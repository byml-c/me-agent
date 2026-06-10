"use client";

import { type ReactNode, useEffect, useRef, useState } from "react";
import { FileText, MessageCircle, X } from "lucide-react";

export type SharedPanelView = "chat" | "node";

type SharedPanelProps = {
  open: boolean;
  view: SharedPanelView;
  headerControls?: ReactNode;
  children: ReactNode;
  onClose: () => void;
  onViewChange: (view: SharedPanelView) => void;
};

type PanelWindow = {
  x: number;
  y: number;
  width: number;
  height: number;
};

const ghostButtonClass = "grid h-8 w-8 place-items-center rounded-full text-slate-500 transition hover:bg-slate-100 hover:text-slate-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-slate-900/20";

export function SharedPanel({ open, view, headerControls, children, onClose, onViewChange }: SharedPanelProps) {
  const [panelWindow, setPanelWindow] = useState<PanelWindow>({ x: 0, y: 76, width: 480, height: 720 });
  const dragRef = useRef<{ startX: number; startY: number; originX: number; originY: number } | null>(null);

  useEffect(() => {
    setPanelWindow(defaultPanelWindow());
  }, []);

  if (!open) {
    return null;
  }

  function startDrag(event: React.PointerEvent<HTMLDivElement>) {
    const target = event.target as HTMLElement;
    if (target.closest("button,select,input,textarea")) {
      return;
    }
    dragRef.current = {
      startX: event.clientX,
      startY: event.clientY,
      originX: panelWindow.x,
      originY: panelWindow.y
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function moveDrag(event: React.PointerEvent<HTMLDivElement>) {
    if (!dragRef.current) {
      return;
    }
    const nextX = dragRef.current.originX + event.clientX - dragRef.current.startX;
    const nextY = dragRef.current.originY + event.clientY - dragRef.current.startY;
    setPanelWindow((current) => clampPanelWindow({ ...current, x: nextX, y: nextY }));
  }

  function endDrag(event: React.PointerEvent<HTMLDivElement>) {
    dragRef.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  }

  return (
    <section
      className="pointer-events-auto absolute left-auto top-[76px] right-[18px] bottom-[18px] grid w-[min(460px,calc(100vw-36px))] grid-rows-[auto_minmax(0,1fr)] overflow-hidden rounded-[32px] border border-slate-200/80 bg-white/96 shadow-[0_28px_90px_rgba(20,24,22,0.14)] backdrop-blur-2xl resize"
      style={{
        left: panelWindow.x,
        top: panelWindow.y,
        width: panelWindow.width,
        height: panelWindow.height
      }}
    >
      <div
        className="flex min-h-[46px] cursor-move select-none items-center justify-between gap-3 border-b border-slate-200 px-4 py-2 text-[13px] font-semibold text-slate-800"
        onPointerDown={startDrag}
        onPointerMove={moveDrag}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
      >
        <div className="grid min-w-0 flex-1 gap-2">
          <div className="grid grid-cols-2 rounded-full bg-slate-100 p-1">
            <button
              className={`inline-flex h-8 items-center justify-center gap-1.5 rounded-full text-sm font-semibold transition ${view === "chat" ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-800"}`}
              onPointerDown={(event) => event.stopPropagation()}
              onClick={(event) => {
                event.stopPropagation();
                onViewChange("chat");
              }}
              type="button"
            >
              <MessageCircle size={14} />
              Chat
            </button>
            <button
              className={`inline-flex h-8 items-center justify-center gap-1.5 rounded-full text-sm font-semibold transition ${view === "node" ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-800"}`}
              onPointerDown={(event) => event.stopPropagation()}
              onClick={(event) => {
                event.stopPropagation();
                onViewChange("node");
              }}
              type="button"
            >
              <FileText size={14} />
              Node
            </button>
          </div>
          {headerControls}
        </div>
        <button className={ghostButtonClass} title="关闭" onClick={onClose} type="button">
          <X size={16} />
        </button>
      </div>
      {children}
    </section>
  );
}

function defaultPanelWindow(): PanelWindow {
  if (typeof window === "undefined") {
    return { x: 0, y: 48, width: 540, height: 760 };
  }
  const width = Math.min(600, Math.max(460, window.innerWidth * 0.36));
  const y = window.innerHeight < 820 ? 16 : 48;
  const height = Math.min(window.innerHeight - y - 16, Math.max(680, window.innerHeight * 0.88));
  return {
    x: Math.max(16, window.innerWidth - width - 18),
    y,
    width,
    height
  };
}

function clampPanelWindow(windowState: PanelWindow): PanelWindow {
  if (typeof window === "undefined") {
    return windowState;
  }
  const margin = 12;
  const maxX = Math.max(margin, window.innerWidth - 80);
  const maxY = Math.max(margin, window.innerHeight - 80);
  return {
    ...windowState,
    x: Math.min(Math.max(margin, windowState.x), maxX),
    y: Math.min(Math.max(margin, windowState.y), maxY)
  };
}
