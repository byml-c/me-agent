"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import * as d3 from "d3";
import { api } from "@/api/client";
import type { EgoGraph, MeEdge, MeNode } from "@/types";

type Props = {
  anchorId?: string;
  onSelectNode?: (node: MeNode) => void;
  compact?: boolean;
  refreshKey?: number;
};

type SimNode = d3.SimulationNodeDatum & {
  id: string;
  title: string;
  isWorkspace: boolean;
  isAnchor: boolean;
  isArchived: boolean;
  accessCount: number;
  radius: number;
  sourceNode: MeNode;
};

type SimLink = d3.SimulationLinkDatum<SimNode> & {
  id: string;
  weight: number;
  isCandidate: boolean;
};

export function GraphPanel({ anchorId, onSelectNode, compact = false, refreshKey = 0 }: Props) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const simulationRef = useRef<d3.Simulation<SimNode, SimLink> | null>(null);
  const [graph, setGraph] = useState<EgoGraph>({ nodes: [], edges: [] });
  const [selectedAnchor, setSelectedAnchor] = useState<string | undefined>(anchorId);

  useEffect(() => {
    api.nodes.list().then((items) => {
      const initial = anchorId ?? items[0]?.id;
      setSelectedAnchor(initial);
      if (initial) {
        api.nodes.graph(initial).then(setGraph).catch(console.error);
      }
    }).catch(console.error);
  }, [anchorId]);

  useEffect(() => {
    if (anchorId && anchorId !== selectedAnchor) {
      focusNode(anchorId);
    }
    if (anchorId && anchorId === selectedAnchor) {
      api.nodes.graph(anchorId).then(setGraph).catch(console.error);
    }
  }, [anchorId, refreshKey]);

  const simNodes = useMemo<SimNode[]>(
    () =>
      graph.nodes.map((node) => ({
        id: node.id,
        title: node.title,
        isWorkspace: node.is_workspace,
        isAnchor: node.id === selectedAnchor,
        isArchived: node.status === "archived",
        accessCount: node.access_count,
        radius: node.is_workspace ? 28 : node.id === selectedAnchor ? 26 : Math.min(24, 17 + node.access_count),
        sourceNode: node
      })),
    [graph.nodes, selectedAnchor]
  );

  const simLinks = useMemo<SimLink[]>(() => {
    const ids = new Set(simNodes.map((node) => node.id));
    return graph.edges
      .filter((edge) => ids.has(edge.node_a_id) && ids.has(edge.node_b_id))
      .map((edge: MeEdge) => ({
        id: edge.id,
        source: edge.node_a_id,
        target: edge.node_b_id,
        weight: edge.weight,
        isCandidate: edge.is_candidate
      }));
  }, [graph.edges, simNodes]);

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

    const root = svg.append("g").attr("class", "d3-graph-root");
    const grid = root.append("g").attr("class", "d3-grid");
    drawGrid(grid, width, height);

    const linkLayer = root.append("g").attr("class", "d3-links");
    const nodeLayer = root.append("g").attr("class", "d3-nodes");
    const labelLayer = root.append("g").attr("class", "d3-labels");

    const links: SimLink[] = simLinks.map((link) => ({ ...link }));
    const simulationNodes: SimNode[] = simNodes.map((node, index) => ({
      ...node,
      x: width / 2 + Math.cos((index / Math.max(1, simNodes.length)) * Math.PI * 2) * (80 + (node.sourceNode.distance ?? 0) * 80),
      y: height / 2 + Math.sin((index / Math.max(1, simNodes.length)) * Math.PI * 2) * (80 + (node.sourceNode.distance ?? 0) * 80)
    }));

    const simulation = d3.forceSimulation<SimNode>(simulationNodes)
      .force("link", d3.forceLink<SimNode, SimLink>(links).id((node) => node.id).distance((link) => 130 - Math.min(48, link.weight * 10)).strength(0.2))
      .force("charge", d3.forceManyBody<SimNode>().strength((node) => node.isAnchor ? -420 : -260))
      .force("collide", d3.forceCollide<SimNode>().radius((node) => node.radius + 26).iterations(2))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("x", d3.forceX<SimNode>(width / 2).strength(0.035))
      .force("y", d3.forceY<SimNode>(height / 2).strength(0.035))
      .alpha(0.9)
      .alphaDecay(0.035)
      .velocityDecay(0.32);

    const linkSelection = linkLayer
      .selectAll<SVGLineElement, SimLink>("line")
      .data(links)
      .join("line")
      .attr("class", (link) => link.isCandidate ? "d3-link candidate" : "d3-link")
      .attr("stroke-width", (link) => Math.max(0.8, Math.min(2.8, link.weight * 0.72)));

    const nodeSelection = nodeLayer
      .selectAll<SVGCircleElement, SimNode>("circle")
      .data(simulationNodes, (node) => node.id)
      .join("circle")
      .attr("class", (node) => nodeClass(node))
      .attr("r", (node) => node.radius)
      .on("click", (_, node) => {
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
            node.fx = event.x;
            node.fy = event.y;
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
      .attr("class", (node) => node.isAnchor ? "d3-label anchor" : "d3-label")
      .text((node) => node.title);

    nodeSelection
      .on("mouseenter", (_, node) => setHoverState(node.id, linkSelection, nodeSelection, labelSelection))
      .on("mouseleave", () => clearHoverState(linkSelection, nodeSelection, labelSelection));

    simulation.on("tick", () => {
        linkSelection
          .attr("x1", (link) => nodePosition(link.source).x)
          .attr("y1", (link) => nodePosition(link.source).y)
          .attr("x2", (link) => nodePosition(link.target).x)
          .attr("y2", (link) => nodePosition(link.target).y);

        nodeSelection
          .attr("cx", (node) => node.x ?? width / 2)
          .attr("cy", (node) => node.y ?? height / 2);

        labelSelection
          .attr("x", (node) => node.x ?? width / 2)
          .attr("y", (node) => (node.y ?? height / 2) + node.radius + 18);
      });

    simulationRef.current = simulation;

    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.35, 2.4])
      .on("zoom", (event) => {
        root.attr("transform", event.transform.toString());
      });
    svg.call(zoom);

    return () => {
      simulation.stop();
      simulationRef.current = null;
    };
  }, [simNodes, simLinks, onSelectNode]);

  function focusNode(nodeId: string) {
    setSelectedAnchor(nodeId);
    api.nodes.graph(nodeId).then(setGraph).catch(console.error);
  }

  return (
    <div className="grid">
      <div ref={wrapRef} className={compact ? "graph-canvas compact d3-force-canvas" : "graph-canvas d3-force-canvas"}>
        <svg ref={svgRef} className="d3-force-svg" role="img" aria-label="Local force graph" />
      </div>
    </div>
  );
}

function nodeClass(node: SimNode) {
  return [
    "d3-node",
    node.isAnchor ? "anchor" : "",
    node.isWorkspace ? "workspace" : "",
    node.isArchived ? "archived" : ""
  ].filter(Boolean).join(" ");
}

function nodePosition(value: string | number | SimNode) {
  if (typeof value === "object") {
    return { x: value.x ?? 0, y: value.y ?? 0 };
  }
  return { x: 0, y: 0 };
}

function drawGrid(group: d3.Selection<SVGGElement, unknown, null, undefined>, width: number, height: number) {
  const step = 34;
  const vertical = d3.range(0, width + step, step);
  const horizontal = d3.range(0, height + step, step);
  group.selectAll("line.v")
    .data(vertical)
    .join("line")
    .attr("class", "d3-grid-line")
    .attr("x1", (x) => x)
    .attr("x2", (x) => x)
    .attr("y1", 0)
    .attr("y2", height);
  group.selectAll("line.h")
    .data(horizontal)
    .join("line")
    .attr("class", "d3-grid-line")
    .attr("x1", 0)
    .attr("x2", width)
    .attr("y1", (y) => y)
    .attr("y2", (y) => y);
}

function setHoverState(
  nodeId: string,
  links: d3.Selection<SVGLineElement, SimLink, SVGGElement, unknown>,
  nodes: d3.Selection<SVGCircleElement, SimNode, SVGGElement, unknown>,
  labels: d3.Selection<SVGTextElement, SimNode, SVGGElement, unknown>
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
  links.classed("muted", (link) => {
    const source = typeof link.source === "object" ? link.source.id : String(link.source);
    const target = typeof link.target === "object" ? link.target.id : String(link.target);
    return source !== nodeId && target !== nodeId;
  });
  nodes.classed("muted", (node) => !neighborIds.has(node.id));
  labels.classed("muted", (node) => !neighborIds.has(node.id));
}

function clearHoverState(
  links: d3.Selection<SVGLineElement, SimLink, SVGGElement, unknown>,
  nodes: d3.Selection<SVGCircleElement, SimNode, SVGGElement, unknown>,
  labels: d3.Selection<SVGTextElement, SimNode, SVGGElement, unknown>
) {
  links.classed("muted", false);
  nodes.classed("muted", false);
  labels.classed("muted", false);
}
