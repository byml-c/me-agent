import {
  faBook,
  faBriefcase,
  faCode,
  faFileLines,
  faHeart,
  faHouse,
  faLightbulb,
  faListCheck,
  faPenNib,
  faStar
} from "@fortawesome/free-solid-svg-icons";
import type { IconDefinition } from "@fortawesome/fontawesome-svg-core";

export type NodeIconKey = "" | "star" | "lightbulb" | "book" | "briefcase" | "house" | "heart" | "code" | "task" | "file" | "pen";

export type NodeIconOption = {
  key: NodeIconKey;
  label: string;
  icon?: IconDefinition;
};

export const NODE_ICON_OPTIONS: NodeIconOption[] = [
  { key: "", label: "无" },
  { key: "star", label: "星标", icon: faStar },
  { key: "lightbulb", label: "想法", icon: faLightbulb },
  { key: "book", label: "知识", icon: faBook },
  { key: "briefcase", label: "工作", icon: faBriefcase },
  { key: "house", label: "生活", icon: faHouse },
  { key: "heart", label: "关系", icon: faHeart },
  { key: "code", label: "代码", icon: faCode },
  { key: "task", label: "任务", icon: faListCheck },
  { key: "file", label: "文档", icon: faFileLines },
  { key: "pen", label: "写作", icon: faPenNib }
];

export function getNodeIcon(key: unknown) {
  if (typeof key !== "string") {
    return undefined;
  }
  return NODE_ICON_OPTIONS.find((option) => option.key === key)?.icon;
}

export function nodeIconPath(key: unknown) {
  const icon = getNodeIcon(key);
  if (!icon) {
    return undefined;
  }
  const path = icon.icon[4];
  return Array.isArray(path) ? path.join(" ") : path;
}

export function nodeIconViewBox(key: unknown) {
  const icon = getNodeIcon(key);
  if (!icon) {
    return "0 0 512 512";
  }
  return `0 0 ${icon.icon[0]} ${icon.icon[1]}`;
}
