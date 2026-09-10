/** Nodal-centre demo campus — fully offline vector graph. Metres in ENU. */

import type { IRoadGraph, IGraphNode, IGraphEdge } from "../types/index.ts";
import { enuToLla } from "../math.ts";

/** Coventry / Midlands — same geography as IO-VNBD training + APK demo mbtiles. */
export const CAMPUS_ORIGIN = { lat: 52.4095, lon: -1.5969, alt: 182 };

function N(
  id: string,
  e: number,
  n: number,
  u: number,
  kind: IGraphNode["kind"],
): IGraphNode {
  const lla = enuToLla(CAMPUS_ORIGIN, e, n, u);
  return { id, lat: lla.lat, lon: lla.lon, alt: lla.alt, kind };
}

function E(
  id: string,
  from: string,
  to: string,
  nodes: IGraphNode[],
  extra: Partial<IGraphEdge> = {},
): IGraphEdge {
  const a = nodes.find((x) => x.id === from)!;
  const b = nodes.find((x) => x.id === to)!;
  const dE = (b.lon - a.lon) * 111412.84 * Math.cos((a.lat * Math.PI) / 180);
  const dN = (b.lat - a.lat) * 111132.92;
  const length_m = Math.hypot(dE, dN);
  const heading_deg = ((Math.atan2(dE, dN) * 180) / Math.PI + 360) % 360;
  return {
    id,
    from,
    to,
    heading_deg,
    length_m,
    tunnel: false,
    garage: false,
    light_spacing_m: null,
    grade: (b.alt - a.alt) / Math.max(1, length_m),
    lanes: 1,
    ...extra,
  };
}

function buildNodes(): IGraphNode[] {
  return [
    N("gate", 0, 0, 0, "outdoor"),
    N("quad", 40, 80, 0, "outdoor"),
    N("xmark", 40, 20, 0, "outdoor"),
    N("ramp_top", 90, 80, 0, "ramp"),
    N("ramp_bot", 110, 80, -4.5, "ramp"),
    N("g_sw", 110, 40, -4.5, "garage"),
    N("g_se", 170, 40, -4.5, "garage"),
    N("g_ne", 170, 100, -4.5, "garage"),
    N("g_nw", 110, 100, -4.5, "garage"),
    N("g_fork", 140, 70, -4.5, "junction"),
    N("portal_in", 200, 80, 0, "portal"),
    N("tun_mid", 520, 80, -2, "tunnel"),
    N("portal_out", 840, 80, 0, "portal"),
    N("exit_true", 840, 140, 0, "junction"),
    N("exit_wrong", 840, 20, 0, "junction"),
    N("round_n", 40, 160, 0, "outdoor"),
    N("round_e", 80, 120, 0, "outdoor"),
    N("round_s", 40, 80, 0, "outdoor"),
    N("round_w", 0, 120, 0, "outdoor"),
    N("j25", 40, 220, 0, "junction"),
    N("j25a", 10, 280, 0, "outdoor"),
    N("j25b", 80, 275, 0, "outdoor"),
    N("j15", 120, 220, 0, "junction"),
    N("j15a", 150, 285, 0, "outdoor"),
    N("j15b", 175, 270, 0, "outdoor"),
    N("j8", 200, 220, 0, "junction"),
    N("j8a", 220, 290, 0, "outdoor"),
    N("j8b", 235, 285, 0, "outdoor"),
    N("loop_e", 40, -40, 0, "outdoor"),
    N("loop_s", -20, -40, 0, "outdoor"),
    N("loop_w", -20, 20, 0, "outdoor"),
  ];
}

export function campusGraph(): IRoadGraph {
  const nodes = buildNodes();
  const edges: IGraphEdge[] = [
    E("gate_quad", "gate", "quad", nodes),
    E("quad_x", "quad", "xmark", nodes),
    E("x_gate", "xmark", "gate", nodes),
    E("quad_ramp", "quad", "ramp_top", nodes),
    E("ramp_down", "ramp_top", "ramp_bot", nodes, { garage: true }),
    E("bot_sw", "ramp_bot", "g_sw", nodes, { garage: true }),
    E("sw_se", "g_sw", "g_se", nodes, { garage: true }),
    E("se_ne", "g_se", "g_ne", nodes, { garage: true }),
    E("ne_nw", "g_ne", "g_nw", nodes, { garage: true }),
    E("nw_bot", "g_nw", "ramp_bot", nodes, { garage: true }),
    E("sw_fork", "g_sw", "g_fork", nodes, { garage: true }),
    E("fork_se", "g_fork", "g_se", nodes, { garage: true }),
    E("fork_ne", "g_fork", "g_ne", nodes, { garage: true }),
    E("fork_nw", "g_fork", "g_nw", nodes, { garage: true }),
    E("quad_portal", "quad", "portal_in", nodes),
    E("tun", "portal_in", "tun_mid", nodes, { tunnel: true, light_spacing_m: 20 }),
    E("tun2", "tun_mid", "portal_out", nodes, { tunnel: true, light_spacing_m: 20 }),
    E("out_true", "portal_out", "exit_true", nodes),
    E("out_wrong", "portal_out", "exit_wrong", nodes),
    E("quad_rn", "quad", "round_n", nodes),
    E("rn_re", "round_n", "round_e", nodes),
    E("re_rs", "round_e", "round_s", nodes),
    E("rs_rw", "round_s", "round_w", nodes),
    E("rw_rn", "round_w", "round_n", nodes),
    E("rn_j25", "round_n", "j25", nodes),
    E("j25_a", "j25", "j25a", nodes),
    E("j25_b", "j25", "j25b", nodes),
    E("j25_j15", "j25", "j15", nodes),
    E("j15_a", "j15", "j15a", nodes),
    E("j15_b", "j15", "j15b", nodes),
    E("j15_j8", "j15", "j8", nodes),
    E("j8_a", "j8", "j8a", nodes),
    E("j8_b", "j8", "j8b", nodes),
    E("x_loope", "xmark", "loop_e", nodes),
    E("loope_s", "loop_e", "loop_s", nodes),
    E("loops_w", "loop_s", "loop_w", nodes),
    E("loopw_gate", "loop_w", "gate", nodes),
    E("ramp_up", "ramp_bot", "ramp_top", nodes, { garage: true }),
    E("ramp_quad", "ramp_top", "quad", nodes),
  ];
  return { name: "IO-VNBD Midlands (Coventry)", origin: CAMPUS_ORIGIN, nodes, edges };
}

export const ROUTES = {
  act1_handoff: ["gate", "quad", "ramp_top", "ramp_bot", "g_sw", "g_se", "g_ne", "g_nw", "ramp_bot", "ramp_top", "quad", "xmark"],
  act2_bicycle: ["gate", "xmark", "loop_e", "loop_s", "loop_w", "gate", "quad", "round_n", "round_e", "round_s", "round_w", "round_n", "quad", "xmark", "gate"],
  act3_tunnel: ["quad", "portal_in", "tun_mid", "portal_out", "exit_true"],
  act4_branch25: ["round_n", "j25", "j25a"],
  act4_branch15: ["j25", "j15", "j15a"],
  act4_branch8: ["j15", "j8", "j8a"],
  garage_wrong_ramp: ["g_fork", "g_ne"],
  garage_true_ramp: ["g_fork", "g_se"],
} as const;

export function routeEdges(graph: IRoadGraph, nodeIds: readonly string[]): string[] {
  const ids: string[] = [];
  for (let i = 0; i < nodeIds.length - 1; i++) {
    const a = nodeIds[i]!;
    const b = nodeIds[i + 1]!;
    const e = graph.edges.find((x) => x.from === a && x.to === b);
    if (e) ids.push(e.id);
  }
  return ids;
}
