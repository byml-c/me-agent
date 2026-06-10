"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import * as d3 from "d3";
import { api } from "@/api/client";
import { nodeIconPath, nodeIconViewBox } from "@/lib/nodeIcons";
import type { EgoGraph, MeEdge, MeNode, Proposal } from "@/types";

type Props = {
  anchorId?: string;
  onSelectNode?: (node: MeNode) => void;
  onCreateNode?: (node: MeNode) => void;
  compact?: boolean;
  refreshKey?: number;
  reviewProposals?: Proposal[];
};

type SimNode = d3.SimulationNodeDatum & {
  id: string;
  title: string;
  isWorkspace: boolean;
  isAnchor: boolean;
  isArchived: boolean;
  accessCount: number;
  radius: number;
  iconPath?: string;
  iconViewBox: string;
  sourceNode: MeNode;
  isPreview?: boolean;
};

type SimLink = d3.SimulationLinkDatum<SimNode> & {
  id: string;
  weight: number;
  isCandidate: boolean;
  sourceEdge?: MeEdge;
};

type ConnectionState = {
  sourceId: string;
  sourceTitle: string;
};

type GraphMenu =
  | { type: "create-node"; sourceId: string; x: number; y: number }
  | { type: "create-edge"; sourceId: string; targetId: string; x: number; y: number };

const graphRootClass = "grid h-full min-h-0";
const graphCanvasBaseClass = "relative w-full overflow-hidden bg-white";
const graphCanvasCompactClass = "min-h-[360px] h-full";
const graphCanvasExpandedClass = "h-[560px]";
const graphSvgClass = "block h-full w-full";
const graphToastClass = "pointer-events-none absolute left-1/2 top-4 z-20 -translate-x-1/2 rounded-full border border-slate-200/90 bg-white/95 px-3 py-2 text-xs font-semibold text-slate-700 shadow-[0_14px_36px_rgba(20,26,23,0.1)] backdrop-blur-xl";
const graphMenuClass = "absolute z-20 grid min-w-[124px] gap-1 rounded-2xl border border-slate-200/90 bg-white/95 p-1.5 shadow-[0_18px_44px_rgba(20,26,23,0.14)] backdrop-blur-xl";
const graphMenuButtonClass = "h-9 rounded-xl px-3 text-left text-sm text-slate-800 transition hover:bg-slate-100";
const graphNodeBaseClass = "cursor-pointer fill-[#f8faf9] stroke-[rgba(22,30,26,0.12)] stroke-[1px] drop-shadow-[0_12px_18px_rgba(20,26,23,0.12)] transition-[opacity,stroke,stroke-width,transform] duration-150";
const graphNodeAnchorClass = "fill-white stroke-[rgba(17,24,20,0.55)] stroke-[2.2px] drop-shadow-[0_18px_28px_rgba(20,26,23,0.16)]";
const graphNodeWorkspaceClass = "fill-[#f1f6ff] stroke-[rgba(55,82,130,0.18)]";
const graphNodePreviewClass = "fill-[#fffaf2] stroke-[rgba(184,118,43,0.7)] stroke-[2px] [stroke-dasharray:5_5] drop-shadow-[0_18px_28px_rgba(184,118,43,0.16)]";
const graphLabelBaseClass = "pointer-events-none select-none text-[12px] fill-[rgba(27,35,31,0.74)] [paint-order:stroke] [stroke:rgba(255,255,255,0.92)] [stroke-width:4px] [stroke-linejoin:round]";
const graphLabelAnchorClass = "fill-[#111814] font-bold";
const graphLabelPreviewClass = "fill-[#7a4d18]";
const graphIconBaseClass = "pointer-events-none fill-[rgba(28,38,33,0.62)] transition-[opacity,fill] duration-150";
const graphIconAnchorClass = "fill-[rgba(17,24,20,0.82)]";
const graphIconPreviewClass = "fill-[rgba(122,77,24,0.75)]";
const graphLinkBaseClass = "stroke-[rgba(86,104,96,0.26)] [stroke-linecap:round] transition-[opacity,stroke] duration-150";
const graphLinkCandidateClass = "stroke-[rgba(177,118,72,0.42)] [stroke-dasharray:4_8]";
const graphLinkSelectedClass = "!stroke-[rgba(17,24,20,0.46)]";
const graphLinkCandidateSelectedClass = "!stroke-[rgba(177,92,28,0.72)]";
const graphLinkHitClass = "stroke-transparent [stroke-linecap:round] stroke-[18px] cursor-pointer";
const graphDraftLinkClass = "pointer-events-none stroke-[rgba(17,24,20,0.48)] stroke-[2px] [stroke-dasharray:6_7]";
const graphControlDotClass = "cursor-pointer fill-white stroke-[#111814] stroke-[2px] drop-shadow-[0_8px_14px_rgba(20,26,23,0.2)]";
const graphControlDotDeleteClass = "fill-white stroke-[rgba(190,58,48,0.5)]";
const graphControlKindClass = "cursor-pointer fill-none stroke-[#34413a] stroke-[2.2px] [stroke-linecap:round] [stroke-linejoin:round]";
const graphControlTrashClass = "cursor-pointer fill-none stroke-[#be3a30] stroke-[2.4px] [stroke-linecap:round] [stroke-linejoin:round]";
const graphControlTrashEdgeClass = "stroke-[2.2px]";

export function GraphPanel({ anchorId, onSelectNode, onCreateNode, compact = false, refreshKey = 0, reviewProposals = [] }: Props) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const simulationRef = useRef<d3.Simulation<SimNode, SimLink> | null>(null);
  const nodePositionsRef = useRef<Map<string, { x: number; y: number }>>(new Map());
  const zoomTransformRef = useRef<d3.ZoomTransform>(d3.zoomIdentity);
  const hideControlsTimerRef = useRef<number | null>(null);
  const connectionRef = useRef<ConnectionState | null>(null);
  const temporaryLinkRef = useRef<d3.Selection<SVGLineElement, unknown, null, undefined> | null>(null);
  const [graph, setGraph] = useState<EgoGraph>({ nodes: [], edges: [] });
  const [selectedAnchor, setSelectedAnchor] = useState<string | undefined>(anchorId);
  const [menu, setMenu] = useState<GraphMenu | null>(null);
  const [connectingLabel, setConnectingLabel] = useState<string | null>(null);

  useEffect(() => {
    refreshGraph().catch(console.error);
  }, [refreshKey]);

  async function refreshGraph() {
    const fullGraph = await api.nodes.fullGraph();
      setGraph(fullGraph);
      setSelectedAnchor((current) => anchorId ?? current ?? fullGraph.nodes[0]?.id);
  }

  useEffect(() => {
    if (anchorId) {
      focusNode(anchorId);
    }
  }, [anchorId]);

  const simNodes = useMemo<SimNode[]>(
    () => {
      const baseNodes = graph.nodes.map((node) => ({
        id: node.id,
        title: node.title,
        isWorkspace: node.is_workspace,
        isAnchor: node.id === selectedAnchor,
        isArchived: node.status === "archived",
        accessCount: node.access_count,
        radius: node.is_workspace ? 28 : node.id === selectedAnchor ? 26 : Math.min(24, 17 + node.access_count),
        iconPath: nodeIconPath(node.memory?.icon),
        iconViewBox: nodeIconViewBox(node.memory?.icon),
        sourceNode: node
      }));
      const previewNodes = reviewProposals
        .filter((proposal) => proposal.operation === "create_node")
        .map((proposal, index) => {
          const payload = proposal.payload as { title?: string; body?: string; is_workspace?: boolean };
          const node: MeNode = {
            id: `preview_${proposal.id}`,
            title: payload.title || "新节点",
            body: payload.body || "",
            summary: null,
            memory: {},
            is_workspace: Boolean(payload.is_workspace),
            status: "active",
            created_at: proposal.created_at,
            updated_at: proposal.created_at,
            last_accessed_at: null,
            access_count: 0,
            distance: 1 + index * 0.1
          };
          return {
            id: node.id,
            title: node.title,
            isWorkspace: node.is_workspace,
            isAnchor: false,
            isArchived: false,
            accessCount: 0,
            radius: node.is_workspace ? 28 : 22,
            iconPath: nodeIconPath(node.memory?.icon),
            iconViewBox: nodeIconViewBox(node.memory?.icon),
            sourceNode: node,
            isPreview: true
          };
        });
      return [...baseNodes, ...previewNodes];
    },
    [graph.nodes, selectedAnchor, reviewProposals]
  );

  const simLinks = useMemo<SimLink[]>(() => {
    const ids = new Set(simNodes.map((node) => node.id));
    const baseLinks = graph.edges
      .filter((edge) => ids.has(edge.node_a_id) && ids.has(edge.node_b_id))
      .map((edge: MeEdge) => ({
        id: edge.id,
        source: edge.node_a_id,
        target: edge.node_b_id,
        weight: edge.weight,
        isCandidate: edge.is_candidate,
        sourceEdge: edge
      }));
    const previewLinks = reviewProposals
      .filter((proposal) => proposal.operation === "create_node" && proposal.target_ids[0])
      .map((proposal) => ({
        id: `preview_edge_${proposal.id}`,
        source: proposal.target_ids[0],
        target: `preview_${proposal.id}`,
        weight: 0.6,
        isCandidate: true
      }))
      .filter((link) => ids.has(String(link.source)) && ids.has(String(link.target)));
    const proposalEdgeLinks = reviewProposals
      .filter((proposal) => proposal.operation === "create_edge")
      .map((proposal) => {
        const payload = proposal.payload as { node_a_id?: string; node_b_id?: string; weight?: number };
        return {
          id: `preview_edge_${proposal.id}`,
          source: payload.node_a_id || proposal.target_ids[0],
          target: payload.node_b_id || proposal.target_ids[1],
          weight: payload.weight ?? 0.6,
          isCandidate: true
        };
      })
      .filter((link) => ids.has(String(link.source)) && ids.has(String(link.target)));
    return [...baseLinks, ...previewLinks, ...proposalEdgeLinks];
  }, [graph.edges, simNodes, reviewProposals]);

  useEffect(() => {
    const svgElement = svgRef.current;
    const wrapElement = wrapRef.current;
    if (!svgElement || !wrapElement) {
      return;
    }

    const width = wrapElement.clientWidth || 960;
    const height = wrapElement.clientHeight || 720;
    const svg = d3.select(svgElement);
    svg.selectAll("*").remove();
    svg.attr("viewBox", `0 0 ${width} ${height}`);

    const root = svg.append("g").attr("class", "graph-root");
    const grid = root.append("g").attr("class", "graph-grid");
    drawGrid(grid, width, height);

    const linkLayer = root.append("g").attr("class", "graph-links");
    const draftLayer = root.append("g").attr("class", "graph-draft-links");
    const nodeLayer = root.append("g").attr("class", "graph-nodes");
    const iconLayer = root.append("g").attr("class", "graph-icons");
    const labelLayer = root.append("g").attr("class", "graph-labels");
    const controlsLayer = root.append("g").attr("class", "graph-node-controls");
    const edgeControlsLayer = root.append("g").attr("class", "graph-edge-controls");

    const links: SimLink[] = simLinks.map((link) => ({ ...link }));
    const hadPositions = nodePositionsRef.current.size > 0;
    const simulationNodes: SimNode[] = simNodes.map((node, index) => {
      const cached = nodePositionsRef.current.get(node.id);
      return {
        ...node,
        x: cached?.x ?? width / 2 + Math.cos((index / Math.max(1, simNodes.length)) * Math.PI * 2) * (80 + (node.sourceNode.distance ?? 0) * 80),
        y: cached?.y ?? height / 2 + Math.sin((index / Math.max(1, simNodes.length)) * Math.PI * 2) * (80 + (node.sourceNode.distance ?? 0) * 80)
      };
    });

    const simulation = d3.forceSimulation<SimNode>(simulationNodes)
      .force("link", d3.forceLink<SimNode, SimLink>(links).id((node) => node.id).distance((link) => 130 - Math.min(48, link.weight * 10)).strength(0.2))
      .force("charge", d3.forceManyBody<SimNode>().strength((node) => node.isAnchor ? -420 : -260))
      .force("collide", d3.forceCollide<SimNode>().radius((node) => node.radius + 26).iterations(2))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("x", d3.forceX<SimNode>(width / 2).strength(0.035))
      .force("y", d3.forceY<SimNode>(height / 2).strength(0.035))
      .alpha(hadPositions ? 0.28 : 0.9)
      .alphaDecay(0.035)
      .velocityDecay(0.32);

    const linkSelection = linkLayer
      .selectAll<SVGLineElement, SimLink>("line")
      .data(links)
      .join("line")
      .attr("data-link", "true")
      .attr("class", (link) => [graphLinkBaseClass, link.isCandidate ? graphLinkCandidateClass : ""].filter(Boolean).join(" "))
      .attr("stroke-width", (link) => Math.max(0.8, Math.min(2.8, link.weight * 0.72)));

    const linkHitSelection = linkLayer
      .selectAll<SVGLineElement, SimLink>('line[data-hit="true"]')
      .data(links.filter((link) => link.sourceEdge), (link) => link.id)
      .join("line")
      .attr("data-hit", "true")
      .attr("class", graphLinkHitClass);

    const edgeControlSelection = edgeControlsLayer
      .selectAll<SVGGElement, SimLink>("g")
      .data(links.filter((link) => link.sourceEdge), (link) => link.id)
      .join("g")
      .attr("class", "hidden");

    edgeControlSelection
      .append("circle")
      .attr("class", graphControlDotClass)
      .attr("r", 11)
      .attr("cx", -14)
      .attr("cy", 0)
      .on("click", (event, link) => {
        event.stopPropagation();
        hideEdgeControls(edgeControlSelection, linkSelection);
        toggleEdgeKind(link).catch(console.error);
      });

    edgeControlSelection
      .append("g")
      .attr("class", graphControlKindClass)
      .attr("transform", "translate(-21,-7) scale(0.58)")
      .html('<path d="M4 12h16"/><path d="M8 8l-4 4 4 4"/><path d="M16 8l4 4-4 4"/>')
      .on("click", (event, link) => {
        event.stopPropagation();
        hideEdgeControls(edgeControlSelection, linkSelection);
        toggleEdgeKind(link).catch(console.error);
      });

    edgeControlSelection
      .append("circle")
      .attr("class", `${graphControlDotClass} ${graphControlDotDeleteClass}`)
      .attr("r", 11)
      .attr("cx", 14)
      .attr("cy", 0)
      .on("click", (event, link) => {
        event.stopPropagation();
        hideEdgeControls(edgeControlSelection, linkSelection);
        deleteEdge(link).catch(console.error);
      });

    edgeControlSelection
      .append("g")
      .attr("class", `${graphControlTrashClass} ${graphControlTrashEdgeClass}`)
      .attr("transform", "translate(7,-7) scale(0.58)")
      .html('<path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/>')
      .on("click", (event, link) => {
        event.stopPropagation();
        hideEdgeControls(edgeControlSelection, linkSelection);
        deleteEdge(link).catch(console.error);
      });

    const nodeSelection = nodeLayer
      .selectAll<SVGCircleElement, SimNode>("circle")
      .data(simulationNodes, (node) => node.id)
      .join("circle")
      .attr("class", (node) => nodeClass(node))
      .attr("r", (node) => node.radius)
      .on("click", (event, node) => {
        event.stopPropagation();
        hideEdgeControls(edgeControlSelection, linkSelection);
        const connection = connectionRef.current;
        if (connection && connection.sourceId !== node.id && !node.isPreview) {
          const [x, y] = d3.pointer(event, wrapElement);
          setMenu({ type: "create-edge", sourceId: connection.sourceId, targetId: node.id, x, y });
          clearConnection();
          return;
        }
        onSelectNode?.(node.sourceNode);
        focusNode(node.id);
      })
      .call(
        d3.drag<SVGCircleElement, SimNode>()
          .on("start", (event, node) => {
            if (!event.active) {
              simulation.alphaTarget(0.28).restart();
            }
            node.fx = node.x;
            node.fy = node.y;
          })
          .on("drag", (event, node) => {
            const rootNode = root.node();
            if (!rootNode) {
              return;
            }
            const [x, y] = d3.pointer(event.sourceEvent, rootNode);
            node.fx = x;
            node.fy = y;
          })
          .on("end", (event, node) => {
            if (!event.active) {
              simulation.alphaTarget(0);
            }
            node.fx = null;
            node.fy = null;
          })
      );

    const labelSelection = labelLayer
      .selectAll<SVGTextElement, SimNode>("text")
      .data(simulationNodes, (node) => node.id)
      .join("text")
      .attr("class", (node) => [graphLabelBaseClass, node.isAnchor ? graphLabelAnchorClass : "", node.isPreview ? graphLabelPreviewClass : ""].filter(Boolean).join(" "))
      .text((node) => node.title);

    const iconSelection = iconLayer
      .selectAll<SVGPathElement, SimNode>("path")
      .data(simulationNodes.filter((node) => node.iconPath), (node) => node.id)
      .join("path")
      .attr("class", (node) => [graphIconBaseClass, node.isAnchor ? graphIconAnchorClass : "", node.isPreview ? graphIconPreviewClass : ""].filter(Boolean).join(" "))
      .attr("d", (node) => node.iconPath ?? "")
      .attr("data-viewbox", (node) => node.iconViewBox);

    const controlSelection = controlsLayer
      .selectAll<SVGGElement, SimNode>("g")
      .data(simulationNodes.filter((node) => !node.isPreview), (node) => node.id)
      .join("g")
      .attr("class", "hidden");

    controlSelection
      .append("circle")
      .attr("class", graphControlDotClass)
      .attr("r", 11)
      .attr("cx", 18)
      .attr("cy", -18)
      .on("click", (event, node) => {
        event.stopPropagation();
        startConnection(node, draftLayer);
      });

    controlSelection
      .append("g")
      .attr("class", "fill-none stroke-[#111814] stroke-[1.8px] [stroke-linecap:round]")
      .attr("transform", "translate(11,-25) scale(0.58)")
      .html('<path d="M12 5v14"/><path d="M5 12h14"/>')
      .on("click", (event, node) => {
        event.stopPropagation();
        startConnection(node, draftLayer);
      });

    controlSelection
      .append("circle")
      .attr("class", `${graphControlDotClass} ${graphControlDotDeleteClass}`)
      .attr("r", 11)
      .attr("cx", -18)
      .attr("cy", -18)
      .on("click", (event, node) => {
        event.stopPropagation();
        deleteNode(node.sourceNode);
      });

    controlSelection
      .append("g")
      .attr("class", graphControlTrashClass)
      .attr("transform", "translate(-25,-25) scale(0.58)")
      .html('<path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/>')
      .on("click", (event, node) => {
        event.stopPropagation();
        deleteNode(node.sourceNode);
      });

    nodeSelection
      .on("mouseenter", (_, node) => {
        cancelHideControls();
        setHoverState(node.id, linkSelection, nodeSelection, labelSelection, iconSelection);
        controlSelection.classed("hidden", (controlNode) => controlNode.id !== node.id);
      })
      .on("mouseleave", () => {
        clearHoverState(linkSelection, nodeSelection, labelSelection, iconSelection);
        scheduleHideControls(controlSelection);
      });

    controlSelection
      .on("mouseenter", (_, node) => {
        cancelHideControls();
        controlSelection.classed("hidden", (controlNode) => controlNode.id !== node.id);
      })
      .on("mouseleave", () => scheduleHideControls(controlSelection));

    linkHitSelection.on("click", (event, link) => {
      event.stopPropagation();
      cancelHideControls();
      linkSelection.classed(graphLinkSelectedClass, (controlLink) => controlLink.id === link.id);
      linkSelection.classed(graphLinkCandidateSelectedClass, (controlLink) => controlLink.id === link.id && controlLink.isCandidate);
      edgeControlSelection.classed("hidden", (controlLink) => controlLink.id !== link.id);
    });

    edgeControlSelection.on("click", (event) => {
      event.stopPropagation();
    });

    simulation.on("tick", () => {
        linkSelection
          .attr("x1", (link) => nodePosition(link.source).x)
          .attr("y1", (link) => nodePosition(link.source).y)
          .attr("x2", (link) => nodePosition(link.target).x)
          .attr("y2", (link) => nodePosition(link.target).y);

        linkHitSelection
          .attr("x1", (link) => nodePosition(link.source).x)
          .attr("y1", (link) => nodePosition(link.source).y)
          .attr("x2", (link) => nodePosition(link.target).x)
          .attr("y2", (link) => nodePosition(link.target).y);

        edgeControlSelection.attr("transform", (link) => {
          const source = nodePosition(link.source);
          const target = nodePosition(link.target);
          return `translate(${(source.x + target.x) / 2},${(source.y + target.y) / 2})`;
        });

        nodeSelection
          .attr("cx", (node) => node.x ?? width / 2)
          .attr("cy", (node) => node.y ?? height / 2);
        nodeSelection.each((node) => {
          nodePositionsRef.current.set(node.id, { x: node.x ?? width / 2, y: node.y ?? height / 2 });
        });

        labelSelection
          .attr("x", (node) => node.x ?? width / 2)
          .attr("y", (node) => (node.y ?? height / 2) + node.radius + 18);

        iconSelection.attr("transform", (node) => iconTransform(node));

        controlSelection.attr("transform", (node) => `translate(${node.x ?? width / 2},${node.y ?? height / 2})`);

        const connection = connectionRef.current;
        if (connection && temporaryLinkRef.current) {
          const source = simulationNodes.find((node) => node.id === connection.sourceId);
          if (source) {
            temporaryLinkRef.current
              .attr("x1", source.x ?? width / 2)
              .attr("y1", source.y ?? height / 2);
          }
        }
      });

    simulationRef.current = simulation;

    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.35, 2.4])
      .on("zoom", (event) => {
        zoomTransformRef.current = event.transform;
        root.attr("transform", event.transform.toString());
      });
    svg.call(zoom);
    root.attr("transform", zoomTransformRef.current.toString());
    svg.call(zoom.transform, zoomTransformRef.current);
    svg.on("click", (event) => {
      hideEdgeControls(edgeControlSelection, linkSelection);
      const connection = connectionRef.current;
      if (!connection) {
        setMenu(null);
        return;
      }
      const [graphX, graphY] = d3.pointer(event, root.node() as SVGGElement);
      const [x, y] = d3.pointer(event, wrapElement);
      temporaryLinkRef.current?.attr("x2", graphX).attr("y2", graphY);
      setMenu({ type: "create-node", sourceId: connection.sourceId, x, y });
      clearConnection(false);
    });
    svg.on("mousemove", (event) => {
      if (!connectionRef.current || !temporaryLinkRef.current) {
        return;
      }
      const [graphX, graphY] = d3.pointer(event, root.node() as SVGGElement);
      temporaryLinkRef.current.attr("x2", graphX).attr("y2", graphY);
    });
    svg.on("keydown", (event) => {
      if (!connectionRef.current) {
        return;
      }
      if (event.key === "Tab") {
        event.preventDefault();
        const connection = connectionRef.current;
        clearConnection();
        createConnectedNodeFromSource(connection.sourceId, event.shiftKey).catch(console.error);
      }
    });
    svg.attr("tabindex", 0);

    return () => {
      simulation.stop();
      simulationRef.current = null;
      temporaryLinkRef.current = null;
      if (hideControlsTimerRef.current) {
        window.clearTimeout(hideControlsTimerRef.current);
        hideControlsTimerRef.current = null;
      }
    };
  }, [simNodes, simLinks, onSelectNode]);

  function focusNode(nodeId: string) {
    setSelectedAnchor(nodeId);
  }

  function cancelHideControls() {
    if (hideControlsTimerRef.current) {
      window.clearTimeout(hideControlsTimerRef.current);
      hideControlsTimerRef.current = null;
    }
  }

  function scheduleHideControls(selection: d3.Selection<SVGGElement, SimNode, SVGGElement, unknown>) {
    cancelHideControls();
    hideControlsTimerRef.current = window.setTimeout(() => {
      selection.classed("hidden", true);
      hideControlsTimerRef.current = null;
    }, 120);
  }

  function hideEdgeControls(
    controls: d3.Selection<SVGGElement, SimLink, SVGGElement, unknown>,
    links: d3.Selection<SVGLineElement, SimLink, SVGGElement, unknown>
  ) {
    cancelHideControls();
    controls.classed("hidden", true);
    links.classed(graphLinkSelectedClass, false);
    links.classed(graphLinkCandidateSelectedClass, false);
  }

  function startConnection(node: SimNode, draftLayer: d3.Selection<SVGGElement, unknown, null, undefined>) {
    clearConnection();
    connectionRef.current = { sourceId: node.id, sourceTitle: node.title };
    setConnectingLabel(node.title);
    setMenu(null);
    svgRef.current?.focus();
    temporaryLinkRef.current = draftLayer
      .append("line")
      .attr("class", graphDraftLinkClass)
      .attr("x1", node.x ?? 0)
      .attr("y1", node.y ?? 0)
      .attr("x2", node.x ?? 0)
      .attr("y2", node.y ?? 0);
  }

  function clearConnection(removeLine = true) {
    connectionRef.current = null;
    setConnectingLabel(null);
    if (removeLine) {
      temporaryLinkRef.current?.remove();
    }
    temporaryLinkRef.current = null;
  }

  async function createConnectedNode(isWorkspace: boolean) {
    if (!menu || menu.type !== "create-node") {
      return;
    }
    await createConnectedNodeFromSource(menu.sourceId, isWorkspace);
    setMenu(null);
  }

  async function createConnectedNodeFromSource(sourceId: string, isWorkspace: boolean) {
    const node = await api.nodes.create({
      title: isWorkspace ? "新工作区" : "新节点",
      body: "",
      is_workspace: isWorkspace
    });
    await api.edges.create({
      node_a_id: sourceId,
      node_b_id: node.id,
      weight: isWorkspace ? 0.9 : 0.7,
      is_candidate: false
    });
    await refreshGraph();
    onSelectNode?.(node);
    focusNode(node.id);
    onCreateNode?.(node);
    return node;
  }

  async function createEdge(isReference: boolean) {
    if (!menu || menu.type !== "create-edge") {
      return;
    }
    await api.edges.create({
      node_a_id: menu.sourceId,
      node_b_id: menu.targetId,
      weight: isReference ? 0.35 : 0.9,
      is_candidate: isReference
    });
    setMenu(null);
    await refreshGraph();
  }

  async function toggleEdgeKind(link: SimLink) {
    const edge = link.sourceEdge;
    if (!edge) {
      return;
    }
    await api.edges.update(edge.id, {
      is_candidate: !edge.is_candidate,
      weight: edge.is_candidate ? 0.9 : 0.35
    });
    await refreshGraph();
  }

  async function deleteEdge(link: SimLink) {
    const edge = link.sourceEdge;
    if (!edge) {
      return;
    }
    if (!window.confirm("删除这条边？")) {
      return;
    }
    await api.edges.delete(edge.id);
    await refreshGraph();
  }

  async function deleteNode(node: MeNode) {
    if (!window.confirm(`删除节点“${node.title}”？节点会被归档并从当前图中隐藏。`)) {
      return;
    }
    await api.nodes.update(node.id, { status: "archived" });
    setMenu(null);
    await refreshGraph();
  }

    return (
      <div className={graphRootClass}>
        <div
          ref={wrapRef}
          className={`${graphCanvasBaseClass} ${compact ? graphCanvasCompactClass : graphCanvasExpandedClass}`}
        >
          <svg ref={svgRef} className={graphSvgClass} role="img" aria-label="Local force graph" />
          {connectingLabel ? <div className={graphToastClass}>从 {connectingLabel} 连线</div> : null}
          {menu ? (
            <div className={graphMenuClass} style={{ left: menu.x, top: menu.y }}>
              {menu.type === "create-node" ? (
                <>
                  <button className={graphMenuButtonClass} onClick={() => createConnectedNode(false)}>普通节点</button>
                  <button className={graphMenuButtonClass} onClick={() => createConnectedNode(true)}>工作区</button>
                </>
              ) : (
                <>
                  <button className={graphMenuButtonClass} onClick={() => createEdge(false)}>普通边</button>
                  <button className={graphMenuButtonClass} onClick={() => createEdge(true)}>参考边</button>
                </>
              )}
            </div>
          ) : null}
        </div>
      </div>
    );
  }

function nodeClass(node: SimNode) {
  return [
    graphNodeBaseClass,
    node.isAnchor ? graphNodeAnchorClass : "",
    node.isWorkspace ? graphNodeWorkspaceClass : "",
    node.isArchived ? "opacity-45" : "",
    node.isPreview ? graphNodePreviewClass : ""
  ].filter(Boolean).join(" ");
}

function nodePosition(value: string | number | SimNode) {
  if (typeof value === "object") {
    return { x: value.x ?? 0, y: value.y ?? 0 };
  }
  return { x: 0, y: 0 };
}

function iconTransform(node: SimNode) {
  const [,, width, height] = node.iconViewBox.split(" ").map(Number);
  const size = node.radius * 0.72;
  const scale = size / Math.max(width || 512, height || 512);
  const x = (node.x ?? 0) - ((width || 512) * scale) / 2;
  const y = (node.y ?? 0) - ((height || 512) * scale) / 2;
  return `translate(${x},${y}) scale(${scale})`;
}

function drawGrid(group: d3.Selection<SVGGElement, unknown, null, undefined>, width: number, height: number) {
  const step = 34;
  const vertical = d3.range(0, width + step, step);
  const horizontal = d3.range(0, height + step, step);
  group.selectAll("line.v")
    .data(vertical)
    .join("line")
    .attr("class", "stroke-slate-200/60 stroke-[1px]")
    .attr("x1", (x) => x)
    .attr("x2", (x) => x)
    .attr("y1", 0)
    .attr("y2", height);
  group.selectAll("line.h")
    .data(horizontal)
    .join("line")
    .attr("class", "stroke-slate-200/60 stroke-[1px]")
    .attr("x1", 0)
    .attr("x2", width)
    .attr("y1", (y) => y)
    .attr("y2", (y) => y);
}

function setHoverState(
  nodeId: string,
  links: d3.Selection<SVGLineElement, SimLink, SVGGElement, unknown>,
  nodes: d3.Selection<SVGCircleElement, SimNode, SVGGElement, unknown>,
  labels: d3.Selection<SVGTextElement, SimNode, SVGGElement, unknown>,
  icons: d3.Selection<SVGPathElement, SimNode, SVGGElement, unknown>
) {
  const neighborIds = new Set<string>([nodeId]);
  links.each((link) => {
    const source = typeof link.source === "object" ? link.source.id : String(link.source);
    const target = typeof link.target === "object" ? link.target.id : String(link.target);
    if (source === nodeId) {
      neighborIds.add(target);
    }
    if (target === nodeId) {
      neighborIds.add(source);
    }
  });
  links.classed("opacity-20", (link) => {
    const source = typeof link.source === "object" ? link.source.id : String(link.source);
    const target = typeof link.target === "object" ? link.target.id : String(link.target);
    return source !== nodeId && target !== nodeId;
  });
  nodes.classed("opacity-20", (node) => !neighborIds.has(node.id));
  labels.classed("opacity-20", (node) => !neighborIds.has(node.id));
  icons.classed("opacity-20", (node) => !neighborIds.has(node.id));
}

function clearHoverState(
  links: d3.Selection<SVGLineElement, SimLink, SVGGElement, unknown>,
  nodes: d3.Selection<SVGCircleElement, SimNode, SVGGElement, unknown>,
  labels: d3.Selection<SVGTextElement, SimNode, SVGGElement, unknown>,
  icons: d3.Selection<SVGPathElement, SimNode, SVGGElement, unknown>
) {
  links.classed("opacity-20", false);
  nodes.classed("opacity-20", false);
  labels.classed("opacity-20", false);
  icons.classed("opacity-20", false);
}
