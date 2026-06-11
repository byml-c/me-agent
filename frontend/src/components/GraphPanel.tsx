"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";
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
  showDirectedEdges?: boolean;
  showCutpointGroups?: boolean;
  editMode?: boolean;
};

type SimNode = d3.SimulationNodeDatum & {
  id: string;
  title: string;
  isWorkspace: boolean;
  isAnchor: boolean;
  isDense: boolean;
  isArchived: boolean;
  accessCount: number;
  radius: number;
  iconPath?: string;
  iconViewBox: string;
  sourceNode: MeNode;
  isPreview?: boolean;
  isGroup?: boolean;
  groupId?: string;
  cutpointId?: string;
  memberIds?: string[];
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

type UndoAction =
  | { type: "restore-node"; node: MeNode }
  | { type: "restore-edge"; edge: MeEdge };

type GraphGroup = {
  id: string;
  cutpointId: string;
  childId: string;
  title: string;
  nodeIds: string[];
};

const graphRootClass = "grid h-full min-h-0";
const graphCanvasBaseClass = "relative w-full overflow-hidden bg-white";
const graphCanvasCompactClass = "min-h-[360px] h-full";
const graphCanvasExpandedClass = "h-[560px]";
const graphSvgClass = "block h-full w-full";
const graphToastClass = "pointer-events-none absolute left-1/2 top-4 z-20 -translate-x-1/2 rounded-full border border-slate-200/90 bg-white/95 px-3 py-2 text-xs font-semibold text-slate-700 shadow-[0_14px_36px_rgba(20,26,23,0.1)] backdrop-blur-xl";
const graphMenuClass = "absolute z-20 grid min-w-[124px] gap-1 rounded-2xl border border-slate-200/90 bg-white/95 p-1.5 shadow-[0_18px_44px_rgba(20,26,23,0.14)] backdrop-blur-xl";
const graphMenuButtonClass = "h-9 rounded-xl px-3 text-left text-sm text-slate-800 transition hover:bg-slate-100";
const graphNodeBaseClass = "me-graph-node cursor-pointer drop-shadow-[0_12px_18px_rgba(20,26,23,0.12)] transition-[opacity,stroke,stroke-width,transform] duration-150";
const graphNodeAnchorClass = "me-graph-node--anchor drop-shadow-[0_18px_28px_rgba(20,26,23,0.16)]";
const graphNodeWorkspaceClass = "me-graph-node--workspace";
const graphNodeDenseClass = "me-graph-node--dense";
const graphNodePreviewClass = "me-graph-node--preview drop-shadow-[0_18px_28px_rgba(184,118,43,0.16)]";
const graphNodeGroupClass = "fill-[#f8fafc] stroke-[rgba(15,23,42,0.42)] stroke-[2px] [stroke-dasharray:5_5]";
const graphNodeSelectedClass = "!stroke-[rgba(17,24,39,0.85)] !stroke-[3px]";
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
const graphBatchToolbarClass = "absolute left-4 top-4 z-20 flex flex-wrap items-center gap-2 rounded-full border border-slate-200/90 bg-white/95 px-3 py-2 text-xs font-semibold text-slate-700 shadow-[0_14px_36px_rgba(20,26,23,0.1)] backdrop-blur-xl";
const graphBatchButtonClass = "rounded-full bg-slate-900 px-3 py-1.5 text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-40";
const COLLAPSED_GROUPS_STORAGE_KEY = "me-agent:collapsed-graph-groups";
const NODE_POSITIONS_STORAGE_KEY = "me-agent:graph-node-positions";
const NODE_POSITION_SAVE_INTERVAL_MS = 1200;

export function GraphPanel({ anchorId, onSelectNode, onCreateNode, compact = false, refreshKey = 0, reviewProposals = [], showDirectedEdges = true, showCutpointGroups = true, editMode = false }: Props) {
  const gridPatternId = useId().replaceAll(":", "");
  const arrowMarkerId = `${gridPatternId}-arrow`;
  const svgRef = useRef<SVGSVGElement | null>(null);
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const simulationRef = useRef<d3.Simulation<SimNode, SimLink> | null>(null);
  const nodePositionsRef = useRef<Map<string, { x: number; y: number }>>(new Map());
  const zoomTransformRef = useRef<d3.ZoomTransform>(d3.zoomIdentity);
  const hideControlsTimerRef = useRef<number | null>(null);
  const connectionRef = useRef<ConnectionState | null>(null);
  const temporaryLinkRef = useRef<d3.Selection<SVGLineElement, unknown, null, undefined> | null>(null);
  const lastPositionSaveRef = useRef(0);
  const undoStackRef = useRef<UndoAction[]>([]);
  const [graph, setGraph] = useState<EgoGraph>({ nodes: [], edges: [] });
  const [selectedAnchor, setSelectedAnchor] = useState<string | undefined>(anchorId);
  const [menu, setMenu] = useState<GraphMenu | null>(null);
  const [connectingLabel, setConnectingLabel] = useState<string | null>(null);
  const [selectedNodeIds, setSelectedNodeIds] = useState<string[]>([]);
  const [collapsedGroupIds, setCollapsedGroupIds] = useState<string[]>([]);

  useEffect(() => {
    nodePositionsRef.current = loadStoredNodePositions();
    setCollapsedGroupIds(loadCollapsedGroupIds());
    refreshGraph().catch(console.error);
  }, [refreshKey]);

  async function refreshGraph(preferredAnchorId?: string) {
    const fullGraph = await api.nodes.fullGraph();
      setGraph(fullGraph);
      setSelectedAnchor((current) => preferredAnchorId ?? anchorId ?? current ?? fullGraph.nodes[0]?.id);
  }

  useEffect(() => {
    if (anchorId) {
      setSelectedAnchor(anchorId);
      focusNode(anchorId);
    }
  }, [anchorId]);

  useEffect(() => {
    saveCollapsedGroupIds(collapsedGroupIds);
  }, [collapsedGroupIds]);

  useEffect(() => {
    if (!editMode) {
      setSelectedNodeIds([]);
    }
  }, [editMode]);

  const graphGroups = useMemo(() => computeDownstreamGroups(graph.nodes, graph.edges), [graph.nodes, graph.edges]);

  useEffect(() => {
    if (!selectedAnchor) {
      return;
    }
    setCollapsedGroupIds((items) => {
      const next = items.filter((groupId) => {
        const group = graphGroups.find((item) => item.id === groupId);
        return group?.cutpointId !== selectedAnchor;
      });
      return next.length === items.length ? items : next;
    });
  }, [selectedAnchor, graphGroups]);

  const collapsedGroupSet = useMemo(() => new Set(collapsedGroupIds), [collapsedGroupIds]);
  const collapsedGroups = useMemo(() => graphGroups.filter((group) => collapsedGroupSet.has(group.id)), [graphGroups, collapsedGroupSet]);
  const hiddenNodeIds = useMemo(() => {
    const ids = new Set<string>();
    for (const group of collapsedGroups) {
      for (const nodeId of group.nodeIds) {
        ids.add(nodeId);
      }
    }
    return ids;
  }, [collapsedGroups]);

  const simNodes = useMemo<SimNode[]>(
    () => {
      const baseNodes = graph.nodes.filter((node) => !hiddenNodeIds.has(node.id)).map((node) => ({
        id: node.id,
        title: node.title,
        isWorkspace: node.is_workspace,
        isAnchor: node.id === selectedAnchor,
        isDense: node.status === "dense",
        isArchived: node.status === "archived",
        accessCount: node.access_count,
        radius: node.is_workspace ? 28 : node.id === selectedAnchor ? 26 : Math.min(24, 17 + node.access_count),
        iconPath: nodeIconPath(node.memory?.icon),
        iconViewBox: nodeIconViewBox(node.memory?.icon),
        sourceNode: node
      }));
      const groupNodes = collapsedGroups.map((group) => {
        const cutpoint = graph.nodes.find((node) => node.id === group.cutpointId) ?? graph.nodes.find((node) => group.nodeIds.includes(node.id));
        const node: MeNode = cutpoint ? { ...cutpoint, title: group.title } : {
          id: group.id,
          title: group.title,
          body: "",
          summary: null,
          memory: {},
          is_workspace: false,
          status: "active",
          created_at: "",
          updated_at: "",
          last_accessed_at: null,
          access_count: 0,
          distance: 0
        };
        return {
          id: group.id,
          title: group.title,
          isWorkspace: false,
          isAnchor: false,
          isDense: false,
          isArchived: false,
          accessCount: 0,
          radius: Math.min(46, 28 + group.nodeIds.length * 2),
          iconPath: undefined,
          iconViewBox: nodeIconViewBox(undefined),
          sourceNode: node,
          isGroup: true,
          groupId: group.id,
          cutpointId: group.cutpointId,
          memberIds: group.nodeIds
        };
      });
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
            isDense: false,
            isArchived: false,
            accessCount: 0,
            radius: node.is_workspace ? 28 : 22,
            iconPath: nodeIconPath(node.memory?.icon),
            iconViewBox: nodeIconViewBox(node.memory?.icon),
            sourceNode: node,
            isPreview: true
          };
        });
      return [...baseNodes, ...groupNodes, ...previewNodes];
    },
    [graph.nodes, hiddenNodeIds, collapsedGroups, selectedAnchor, reviewProposals]
  );

  const simLinks = useMemo<SimLink[]>(() => {
    const ids = new Set(simNodes.map((node) => node.id));
    const groupByHiddenNode = new Map<string, GraphGroup>();
    for (const group of collapsedGroups) {
      for (const nodeId of group.nodeIds) {
        groupByHiddenNode.set(nodeId, group);
      }
    }
    const linkKeys = new Set<string>();
    const baseLinks: SimLink[] = [];
    for (const edge of graph.edges) {
        const sourceGroup = groupByHiddenNode.get(edge.node_a_id);
        const targetGroup = groupByHiddenNode.get(edge.node_b_id);
        const source = sourceGroup?.id ?? edge.node_a_id;
        const target = targetGroup?.id ?? edge.node_b_id;
        if (source === target || !ids.has(source) || !ids.has(target)) {
          continue;
        }
        const key = `${source}->${target}:${edge.is_candidate ? "candidate" : "real"}`;
        if (linkKeys.has(key)) {
          continue;
        }
        linkKeys.add(key);
        baseLinks.push({
          id: sourceGroup || targetGroup ? `${edge.id}_${source}_${target}` : edge.id,
          source,
          target,
          weight: edge.weight,
          isCandidate: edge.is_candidate,
          sourceEdge: sourceGroup || targetGroup ? undefined : edge
        });
    }
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
  }, [graph.edges, simNodes, collapsedGroups, reviewProposals]);

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

    const defs = svg.append("defs");
    defs
      .append("marker")
      .attr("id", arrowMarkerId)
      .attr("viewBox", "0 -5 10 10")
      .attr("refX", 9)
      .attr("refY", 0)
      .attr("markerWidth", 7)
      .attr("markerHeight", 7)
      .attr("orient", "auto")
      .append("path")
      .attr("d", "M0,-5L10,0L0,5")
      .attr("fill", "rgba(86,104,96,0.46)");
    const gridPattern = defs
      .append("pattern")
      .attr("id", gridPatternId)
      .attr("width", 34)
      .attr("height", 34)
      .attr("patternUnits", "userSpaceOnUse");
    gridPattern
      .append("path")
      .attr("d", "M 34 0 L 0 0 0 34")
      .attr("fill", "none")
      .attr("class", "stroke-slate-200/60 stroke-[1px]");
    svg
      .append("rect")
      .attr("class", "graph-grid-background")
      .attr("width", width)
      .attr("height", height)
      .attr("fill", `url(#${gridPatternId})`);

    const root = svg.append("g").attr("class", "graph-root");

    const groupLayer = root.append("g").attr("class", "graph-groups");
    const linkLayer = root.append("g").attr("class", "graph-links");
    const draftLayer = root.append("g").attr("class", "graph-draft-links");
    const nodeLayer = root.append("g").attr("class", "graph-nodes");
    const iconLayer = root.append("g").attr("class", "graph-icons");
    const labelLayer = root.append("g").attr("class", "graph-labels");
    const controlsLayer = root.append("g").attr("class", "graph-node-controls");
    const edgeControlsLayer = root.append("g").attr("class", "graph-edge-controls");

    const links: SimLink[] = simLinks.map((link) => ({ ...link }));
    const hadPositions = nodePositionsRef.current.size > 0;
    const activeGroupIds = new Set(collapsedGroups.map((group) => group.id));
    const selectedNodeIdSet = new Set(selectedNodeIds);
    const simulationNodes: SimNode[] = simNodes.map((node, index) => {
      const cached = nodePositionsRef.current.get(node.id);
      return {
        ...node,
        x: cached?.x ?? width / 2 + Math.cos((index / Math.max(1, simNodes.length)) * Math.PI * 2) * (80 + (node.sourceNode.distance ?? 0) * 80),
        y: cached?.y ?? height / 2 + Math.sin((index / Math.max(1, simNodes.length)) * Math.PI * 2) * (80 + (node.sourceNode.distance ?? 0) * 80)
      };
    });
    const nodeDegree = degreeByNode(links);

    const simulation = d3.forceSimulation<SimNode>(simulationNodes)
      .force("link", d3.forceLink<SimNode, SimLink>(links).id((node) => node.id).distance((link) => {
        const sourceDegree = nodeDegree.get(linkEndpointId(link.source)) ?? 0;
        const targetDegree = nodeDegree.get(linkEndpointId(link.target)) ?? 0;
        return 155 + Math.min(84, (sourceDegree + targetDegree) * 7) - Math.min(52, link.weight * 12);
      }).strength((link) => link.isCandidate ? 0.08 : 0.12))
      .force("charge", d3.forceManyBody<SimNode>().strength((node) => node.isAnchor ? -760 : node.isWorkspace ? -620 : -500).distanceMin(48).distanceMax(Math.max(width, height) * 0.9))
      .force("collide", d3.forceCollide<SimNode>().radius((node) => node.radius + 44).iterations(3))
      .force("edgeAvoidance", createEdgeAvoidanceForce(links))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("x", d3.forceX<SimNode>(width / 2).strength(0.018))
      .force("y", d3.forceY<SimNode>(height / 2).strength(0.018))
      .alpha(hadPositions ? 0.45 : 1)
      .alphaDecay(0.035)
      .velocityDecay(0.38);

    const linkSelection = linkLayer
      .selectAll<SVGLineElement, SimLink>("line")
      .data(links)
      .join("line")
      .attr("data-link", "true")
      .attr("class", (link) => [graphLinkBaseClass, link.isCandidate ? graphLinkCandidateClass : ""].filter(Boolean).join(" "))
      .attr("stroke-width", (link) => Math.max(0.8, Math.min(2.8, link.weight * 0.72)))
      .attr("marker-end", (link) => showDirectedEdges && !link.isCandidate ? `url(#${arrowMarkerId})` : null);

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
      .attr("cx", -26)
      .attr("cy", 0)
      .on("click", (event, link) => {
        event.stopPropagation();
        hideEdgeControls(edgeControlSelection, linkSelection);
        toggleEdgeKind(link).catch(console.error);
      });

    edgeControlSelection
      .append("g")
      .attr("class", graphControlKindClass)
      .attr("transform", "translate(-33,-7) scale(0.58)")
      .html('<path d="M4 8h16"/><path d="M4 16h3"/><path d="M10 16h3"/><path d="M16 16h4"/>')
      .on("click", (event, link) => {
        event.stopPropagation();
        hideEdgeControls(edgeControlSelection, linkSelection);
        toggleEdgeKind(link).catch(console.error);
      });

    edgeControlSelection
      .append("circle")
      .attr("class", graphControlDotClass)
      .attr("r", 11)
      .attr("cx", 0)
      .attr("cy", 0)
      .classed("hidden", !showDirectedEdges)
      .on("click", (event, link) => {
        event.stopPropagation();
        hideEdgeControls(edgeControlSelection, linkSelection);
        reverseEdge(link).catch(console.error);
      });

    edgeControlSelection
      .append("g")
      .attr("class", graphControlKindClass)
      .attr("transform", "translate(-7,-7) scale(0.58)")
      .classed("hidden", !showDirectedEdges)
      .html('<path d="M7 7h10l-3-3"/><path d="M17 17H7l3 3"/><path d="M17 7l-4 4"/><path d="M7 17l4-4"/>')
      .on("click", (event, link) => {
        event.stopPropagation();
        hideEdgeControls(edgeControlSelection, linkSelection);
        reverseEdge(link).catch(console.error);
      });

    edgeControlSelection
      .append("circle")
      .attr("class", `${graphControlDotClass} ${graphControlDotDeleteClass}`)
      .attr("r", 11)
      .attr("cx", 26)
      .attr("cy", 0)
      .on("click", (event, link) => {
        event.stopPropagation();
        hideEdgeControls(edgeControlSelection, linkSelection);
        deleteEdge(link).catch(console.error);
      });

    edgeControlSelection
      .append("g")
      .attr("class", `${graphControlTrashClass} ${graphControlTrashEdgeClass}`)
      .attr("transform", "translate(19,-7) scale(0.58)")
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
      .attr("class", (node) => nodeClass(node, selectedNodeIdSet))
      .attr("r", (node) => node.radius)
      .on("click", (event, node) => {
        event.stopPropagation();
        svgRef.current?.focus();
        hideEdgeControls(edgeControlSelection, linkSelection);
        if (node.isGroup && node.groupId) {
          setCollapsedGroupIds((items) => items.filter((id) => id !== node.groupId));
          return;
        }
        if (editMode) {
          setSelectedNodeIds((items) => items.includes(node.id) ? items.filter((id) => id !== node.id) : [...items, node.id]);
          return;
        }
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
      .attr("text-anchor", "middle")
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
      .data(simulationNodes.filter((node) => !node.isPreview && !node.isGroup), (node) => node.id)
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
        linkSelection.each(function (link) {
          const segment = linkSegment(link);
          d3.select(this)
            .attr("x1", segment.x1)
            .attr("y1", segment.y1)
            .attr("x2", segment.x2)
            .attr("y2", segment.y2);
        });

        linkHitSelection.each(function (link) {
          const segment = linkSegment(link, 0);
          d3.select(this)
            .attr("x1", segment.x1)
            .attr("y1", segment.y1)
            .attr("x2", segment.x2)
            .attr("y2", segment.y2);
        });

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
        saveNodePositionsSoon(nodePositionsRef.current, lastPositionSaveRef);

        labelSelection
          .attr("x", (node) => node.x ?? width / 2)
          .attr("y", (node) => (node.y ?? height / 2) + node.radius + 18);

        iconSelection.attr("transform", (node) => iconTransform(node));

        controlSelection.attr("transform", (node) => `translate(${node.x ?? width / 2},${node.y ?? height / 2})`);

        renderGroupBoxes(groupLayer, showCutpointGroups ? graphGroups.filter((group) => !activeGroupIds.has(group.id)) : [], simulationNodes, (groupId) => {
          setCollapsedGroupIds((items) => items.includes(groupId) ? items : [...items, groupId]);
        });

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
        gridPattern.attr("patternTransform", event.transform.toString());
        root.attr("transform", event.transform.toString());
      });
    svg.call(zoom);
    gridPattern.attr("patternTransform", zoomTransformRef.current.toString());
    root.attr("transform", zoomTransformRef.current.toString());
    svg.call(zoom.transform, zoomTransformRef.current);
    svg.on("click", (event) => {
      svgRef.current?.focus();
      hideEdgeControls(edgeControlSelection, linkSelection);
      if (editMode) {
        setSelectedNodeIds([]);
      }
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
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z") {
        event.preventDefault();
        undoLastGraphAction().catch(console.error);
        return;
      }
      if (event.key === "Tab") {
        event.preventDefault();
        const connection = connectionRef.current;
        if (connection) {
          clearConnection();
          createConnectedNodeFromSource(connection.sourceId, event.shiftKey).catch(console.error);
          return;
        }
        if (selectedAnchor) {
          createConnectedNodeFromSource(selectedAnchor, event.shiftKey).catch(console.error);
        }
        return;
      }
      if (event.key === "Delete" || event.key === "Backspace") {
        event.preventDefault();
        if (selectedAnchor) {
          deleteSelectedNode(selectedAnchor).catch(console.error);
        }
      }
    });
    svg.attr("tabindex", 0);

    return () => {
      saveStoredNodePositions(nodePositionsRef.current);
      simulation.stop();
      simulationRef.current = null;
      temporaryLinkRef.current = null;
      if (hideControlsTimerRef.current) {
        window.clearTimeout(hideControlsTimerRef.current);
        hideControlsTimerRef.current = null;
      }
    };
  }, [simNodes, simLinks, onSelectNode, selectedAnchor, graph.nodes, graph.edges, graphGroups, collapsedGroups, showDirectedEdges, showCutpointGroups, arrowMarkerId, editMode, selectedNodeIds]);

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
    onSelectNode?.(node);
    focusNode(node.id);
    onCreateNode?.(node);
    await refreshGraph(node.id);
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

  async function reverseEdge(link: SimLink) {
    const edge = link.sourceEdge;
    if (!edge) {
      return;
    }
    await api.edges.update(edge.id, {
      node_a_id: edge.node_b_id,
      node_b_id: edge.node_a_id
    });
    await refreshGraph();
  }

  async function deleteEdge(link: SimLink) {
    const edge = link.sourceEdge;
    if (!edge) {
      return;
    }
    undoStackRef.current.push({ type: "restore-edge", edge });
    await api.edges.delete(edge.id);
    await refreshGraph();
  }

  async function deleteNode(node: MeNode) {
    undoStackRef.current.push({ type: "restore-node", node });
    await api.nodes.update(node.id, { status: "archived" });
    setMenu(null);
    await refreshGraph();
  }

  async function deleteSelectedNode(nodeId: string) {
    const node = graph.nodes.find((item) => item.id === nodeId);
    if (!node || node.status === "archived") {
      return;
    }
    const nextNodeId = nextNodeAfterDelete(nodeId, graph.nodes, graph.edges);
    undoStackRef.current.push({ type: "restore-node", node });
    await api.nodes.update(node.id, { status: "archived" });
    setMenu(null);
    if (nextNodeId) {
      const nextNode = graph.nodes.find((item) => item.id === nextNodeId);
      if (nextNode) {
        onSelectNode?.(nextNode);
      }
      focusNode(nextNodeId);
    }
    await refreshGraph(nextNodeId);
  }

  async function archiveSelectedNodes() {
    if (!selectedNodeIds.length) {
      return;
    }
    await api.nodes.archiveBatch(selectedNodeIds);
    setSelectedNodeIds([]);
    await refreshGraph();
  }

  async function insertNodeBetweenSelected() {
    if (selectedNodeIds.length !== 2) {
      return;
    }
    const result = await api.nodes.insertBetween([selectedNodeIds[0], selectedNodeIds[1]]);
    setSelectedNodeIds([]);
    onSelectNode?.(result.node);
    onCreateNode?.(result.node);
    await refreshGraph(result.node.id);
  }

  async function addCutpointForSelected() {
    if (!selectedNodeIds.length) {
      return;
    }
    const result = await api.nodes.addCutpoint(selectedNodeIds);
    setSelectedNodeIds([]);
    onSelectNode?.(result.node);
    onCreateNode?.(result.node);
    await refreshGraph(result.node.id);
  }

  async function undoLastGraphAction() {
    const action = undoStackRef.current.pop();
    if (!action) {
      return;
    }
    if (action.type === "restore-node") {
      const restored = await api.nodes.update(action.node.id, { status: action.node.status });
      onSelectNode?.(restored);
      focusNode(restored.id);
      await refreshGraph(restored.id);
      return;
    }
    await api.edges.create({
      node_a_id: action.edge.node_a_id,
      node_b_id: action.edge.node_b_id,
      weight: action.edge.weight,
      is_candidate: action.edge.is_candidate
    });
    await refreshGraph();
  }

    return (
      <div className={graphRootClass}>
        <div
          ref={wrapRef}
          className={`${graphCanvasBaseClass} ${compact ? graphCanvasCompactClass : graphCanvasExpandedClass}`}
        >
          <svg ref={svgRef} className={graphSvgClass} role="img" aria-label="Local force graph" />
          {editMode ? (
            <div className={graphBatchToolbarClass}>
              <span>{selectedNodeIds.length ? `已选 ${selectedNodeIds.length} 个节点` : "编辑模式：点击节点多选"}</span>
              <button className={graphBatchButtonClass} onClick={archiveSelectedNodes} disabled={!selectedNodeIds.length} type="button">删除</button>
              <button className={graphBatchButtonClass} onClick={addCutpointForSelected} disabled={!selectedNodeIds.length} type="button">添加割点</button>
              <button className={graphBatchButtonClass} onClick={insertNodeBetweenSelected} disabled={selectedNodeIds.length !== 2} type="button">
                中间插入
              </button>
              <button className="rounded-full bg-slate-100 px-3 py-1.5 text-slate-700 transition hover:bg-slate-200" onClick={() => setSelectedNodeIds([])} type="button">取消</button>
            </div>
          ) : null}
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

function nodeClass(node: SimNode, selectedNodeIds: Set<string> = new Set()) {
  return [
    graphNodeBaseClass,
    node.isAnchor ? graphNodeAnchorClass : "",
    node.isWorkspace ? graphNodeWorkspaceClass : "",
    node.isDense ? graphNodeDenseClass : "",
    node.isArchived ? "opacity-45" : "",
    node.isPreview ? graphNodePreviewClass : "",
    node.isGroup ? graphNodeGroupClass : "",
    selectedNodeIds.has(node.id) ? graphNodeSelectedClass : ""
  ].filter(Boolean).join(" ");
}

function nodePosition(value: string | number | SimNode) {
  if (typeof value === "object") {
    return { x: value.x ?? 0, y: value.y ?? 0 };
  }
  return { x: 0, y: 0 };
}

function linkSegment(link: SimLink, padding = 8) {
  const source = typeof link.source === "object" ? link.source : null;
  const target = typeof link.target === "object" ? link.target : null;
  const sourcePosition = nodePosition(link.source);
  const targetPosition = nodePosition(link.target);
  if (!source || !target) {
    return { x1: sourcePosition.x, y1: sourcePosition.y, x2: targetPosition.x, y2: targetPosition.y };
  }
  const dx = targetPosition.x - sourcePosition.x;
  const dy = targetPosition.y - sourcePosition.y;
  const distance = Math.hypot(dx, dy) || 1;
  const sourceOffset = Math.min(distance / 2, source.radius + padding);
  const targetOffset = Math.min(distance / 2, target.radius + padding);
  return {
    x1: sourcePosition.x + (dx / distance) * sourceOffset,
    y1: sourcePosition.y + (dy / distance) * sourceOffset,
    x2: targetPosition.x - (dx / distance) * targetOffset,
    y2: targetPosition.y - (dy / distance) * targetOffset
  };
}

function linkEndpointId(value: string | number | SimNode) {
  return typeof value === "object" ? value.id : String(value);
}

function degreeByNode(links: SimLink[]) {
  const degree = new Map<string, number>();
  for (const link of links) {
    const source = linkEndpointId(link.source);
    const target = linkEndpointId(link.target);
    degree.set(source, (degree.get(source) ?? 0) + 1);
    degree.set(target, (degree.get(target) ?? 0) + 1);
  }
  return degree;
}

function computeDownstreamGroups(nodes: MeNode[], edges: MeEdge[]): GraphGroup[] {
  const activeNodeIds = new Set(nodes.filter((node) => node.status !== "archived").map((node) => node.id));
  const nodeById = new Map(nodes.map((node) => [node.id, node]));
  const outgoing = new Map<string, string[]>();
  const incomingCount = new Map<string, number>();
  for (const edge of edges) {
    if (edge.is_candidate || !activeNodeIds.has(edge.node_a_id) || !activeNodeIds.has(edge.node_b_id)) {
      continue;
    }
    outgoing.set(edge.node_a_id, [...(outgoing.get(edge.node_a_id) ?? []), edge.node_b_id]);
    incomingCount.set(edge.node_b_id, (incomingCount.get(edge.node_b_id) ?? 0) + 1);
  }
  const groups: GraphGroup[] = [];
  for (const node of nodes) {
    const children = outgoing.get(node.id) ?? [];
    if (children.length < 2) {
      continue;
    }
    for (const childId of children) {
      const branch = collectExclusiveDownstream(childId, node.id, outgoing, incomingCount);
      if (branch.length < 2) {
        continue;
      }
      groups.push({
        id: `${node.id}:${childId}`,
        cutpointId: node.id,
        childId,
        title: nodeById.get(childId)?.title ?? node.title,
        nodeIds: branch
      });
    }
  }
  return groups.sort((a, b) => b.nodeIds.length - a.nodeIds.length);
}

function collectExclusiveDownstream(startId: string, cutpointId: string, outgoing: Map<string, string[]>, incomingCount: Map<string, number>) {
  const result: string[] = [];
  const seen = new Set<string>();
  const stack = [startId];
  while (stack.length) {
    const nodeId = stack.pop()!;
    if (seen.has(nodeId)) {
      continue;
    }
    seen.add(nodeId);
    result.push(nodeId);
    for (const childId of outgoing.get(nodeId) ?? []) {
      if (childId === cutpointId || (incomingCount.get(childId) ?? 0) > 1) {
        continue;
      }
      stack.push(childId);
    }
  }
  return result;
}

function renderGroupBoxes(
  layer: d3.Selection<SVGGElement, unknown, null, undefined>,
  groups: GraphGroup[],
  nodes: SimNode[],
  onCollapse: (groupId: string) => void
) {
  const nodeById = new Map(nodes.map((node) => [node.id, node]));
  const visibleGroups = groups
    .map((group) => {
      const members = group.nodeIds.map((nodeId) => nodeById.get(nodeId)).filter((node): node is SimNode => Boolean(node));
      if (members.length < 2) {
        return null;
      }
      const hull = groupHullPath(members);
      if (!hull) {
        return null;
      }
      const minX = Math.min(...hull.points.map(([x]) => x));
      const minY = Math.min(...hull.points.map(([, y]) => y));
      const maxX = Math.max(...hull.points.map(([x]) => x));
      return { ...group, path: hull.path, labelX: minX + 18, labelY: minY + 22, buttonX: maxX - 20, buttonY: minY + 22 };
    })
    .filter((group): group is GraphGroup & { path: string; labelX: number; labelY: number; buttonX: number; buttonY: number } => Boolean(group));

  const selection = layer.selectAll<SVGGElement, GraphGroup & { path: string; labelX: number; labelY: number; buttonX: number; buttonY: number }>("g").data(visibleGroups, (group) => group.id);
  const entered = selection.enter().append("g").attr("class", "graph-group-box");
  entered
    .append("path")
    .attr("fill", "transparent")
    .attr("stroke", "rgba(148,163,184,0.6)")
    .attr("stroke-width", 1.5)
    .attr("stroke-dasharray", "7 7");
  entered.append("text").attr("class", "graph-group-label select-none text-[11px] font-semibold fill-slate-500");
  entered.append("circle").attr("r", 12).attr("class", "cursor-pointer fill-white stroke-slate-400 stroke-[1.5px]");
  entered.append("text").attr("class", "graph-group-collapse-icon pointer-events-none select-none text-[14px] font-bold fill-slate-600").attr("text-anchor", "middle").attr("dominant-baseline", "central").text("-");
  const merged = entered.merge(selection);
  merged.select("path").attr("d", (group) => group.path);
  merged.select(".graph-group-label").attr("x", (group) => group.labelX).attr("y", (group) => group.labelY).text((group) => `${group.title} · ${group.nodeIds.length}`);
  merged.select("circle").attr("cx", (group) => group.buttonX).attr("cy", (group) => group.buttonY).on("click", (event, group) => {
    event.stopPropagation();
    onCollapse(group.id);
  });
  merged.select(".graph-group-collapse-icon").attr("x", (group) => group.buttonX).attr("y", (group) => group.buttonY);
  selection.exit().remove();
}

function groupHullPath(members: SimNode[]) {
  const points: [number, number][] = [];
  const padding = 26;
  const samples = 12;
  for (const node of members) {
    const radius = node.radius + padding;
    const x = node.x ?? 0;
    const y = node.y ?? 0;
    for (let index = 0; index < samples; index += 1) {
      const angle = (index / samples) * Math.PI * 2;
      points.push([x + Math.cos(angle) * radius, y + Math.sin(angle) * radius]);
    }
  }
  const hull = d3.polygonHull(points);
  if (!hull?.length) {
    return null;
  }
  return {
    points: hull,
    path: `M${hull.map(([x, y]) => `${x},${y}`).join("L")}Z`
  };
}

function nextNodeAfterDelete(nodeId: string, nodes: MeNode[], edges: MeEdge[]) {
  const activeNodeIds = new Set(nodes.filter((node) => node.id !== nodeId && node.status !== "archived").map((node) => node.id));
  const neighborId = edges
    .map((edge) => {
      if (edge.node_a_id === nodeId) {
        return edge.node_b_id;
      }
      if (edge.node_b_id === nodeId) {
        return edge.node_a_id;
      }
      return "";
    })
    .find((id) => id && activeNodeIds.has(id));
  if (neighborId) {
    return neighborId;
  }
  return nodes.find((node) => activeNodeIds.has(node.id))?.id;
}

function loadStoredNodePositions() {
  if (typeof window === "undefined") {
    return new Map<string, { x: number; y: number }>();
  }
  try {
    const raw = window.localStorage.getItem(NODE_POSITIONS_STORAGE_KEY);
    if (!raw) {
      return new Map<string, { x: number; y: number }>();
    }
    const parsed = JSON.parse(raw) as Record<string, { x: number; y: number }>;
    return new Map(
      Object.entries(parsed).filter(([, position]) => Number.isFinite(position.x) && Number.isFinite(position.y))
    );
  } catch {
    return new Map<string, { x: number; y: number }>();
  }
}

function loadCollapsedGroupIds() {
  if (typeof window === "undefined") {
    return [];
  }
  try {
    const raw = window.localStorage.getItem(COLLAPSED_GROUPS_STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter((item): item is string => typeof item === "string") : [];
  } catch {
    return [];
  }
}

function saveCollapsedGroupIds(groupIds: string[]) {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.localStorage.setItem(COLLAPSED_GROUPS_STORAGE_KEY, JSON.stringify(groupIds));
  } catch {
    // Ignore storage failures; collapse is a view preference only.
  }
}

function saveNodePositionsSoon(positions: Map<string, { x: number; y: number }>, lastSaveRef: { current: number }) {
  const now = Date.now();
  if (now - lastSaveRef.current < NODE_POSITION_SAVE_INTERVAL_MS) {
    return;
  }
  lastSaveRef.current = now;
  saveStoredNodePositions(positions);
}

function saveStoredNodePositions(positions: Map<string, { x: number; y: number }>) {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.localStorage.setItem(
      NODE_POSITIONS_STORAGE_KEY,
      JSON.stringify(Object.fromEntries(positions))
    );
  } catch {
    // Ignore storage failures; graph layout should still work without persistence.
  }
}

function createEdgeAvoidanceForce(links: SimLink[]): d3.Force<SimNode, SimLink> {
  let nodes: SimNode[] = [];

  function force(alpha: number) {
    const strength = 0.22 * alpha;
    for (const node of nodes) {
      const nodeX = node.x ?? 0;
      const nodeY = node.y ?? 0;
      for (const link of links) {
        const source = typeof link.source === "object" ? link.source : null;
        const target = typeof link.target === "object" ? link.target : null;
        if (!source || !target || source.id === node.id || target.id === node.id) {
          continue;
        }

        const projection = projectedPointOnSegment(nodeX, nodeY, source.x ?? 0, source.y ?? 0, target.x ?? 0, target.y ?? 0);
        const dx = nodeX - projection.x;
        const dy = nodeY - projection.y;
        const distance = Math.hypot(dx, dy) || 1;
        const clearance = node.radius + 28;
        if (distance >= clearance) {
          continue;
        }

        const push = (clearance - distance) * strength;
        node.vx = (node.vx ?? 0) + (dx / distance) * push;
        node.vy = (node.vy ?? 0) + (dy / distance) * push;
      }
    }
  }

  force.initialize = (initializedNodes: SimNode[]) => {
    nodes = initializedNodes;
  };

  return force;
}

function projectedPointOnSegment(px: number, py: number, ax: number, ay: number, bx: number, by: number) {
  const dx = bx - ax;
  const dy = by - ay;
  const lengthSquared = dx * dx + dy * dy;
  if (!lengthSquared) {
    return { x: ax, y: ay };
  }
  const t = Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / lengthSquared));
  return { x: ax + t * dx, y: ay + t * dy };
}

function iconTransform(node: SimNode) {
  const [,, width, height] = node.iconViewBox.split(" ").map(Number);
  const size = node.radius * 0.72;
  const scale = size / Math.max(width || 512, height || 512);
  const x = (node.x ?? 0) - ((width || 512) * scale) / 2;
  const y = (node.y ?? 0) - ((height || 512) * scale) / 2;
  return `translate(${x},${y}) scale(${scale})`;
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
