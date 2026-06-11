import type { Dispatch, SetStateAction } from "react";
import type { MeNode, NodeAttachments, NodeDatabaseAttachment, NodeScriptAttachment } from "@/types";
import type { NodeIconKey } from "@/lib/nodeIcons";

export type NodeEditorDraft = {
  title: string;
  summary: string;
  body: string;
  icon: NodeIconKey;
  attachments: NodeAttachments;
  is_workspace: boolean;
  status: MeNode["status"];
};

export type LongTextEditorTarget =
  | { kind: "summary" }
  | { kind: "body" }
  | { kind: "database"; id?: string }
  | { kind: "script"; id?: string };

export type DraftChange = Dispatch<SetStateAction<NodeEditorDraft | null>>;

export function databaseTitle(database: NodeDatabaseAttachment) {
  return database.name || "知识条目";
}

export function scriptTitle(script: NodeScriptAttachment) {
  return script.name || "Python 脚本";
}
