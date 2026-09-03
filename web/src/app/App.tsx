import { useEffect, useState } from "react";
import { Landing } from "./Landing";
import { Console } from "./Console";
import { EvidenceRoom } from "./EvidenceRoom";
import { Operations } from "./Operations";
import type { ActId } from "../lib/runDemo";

type View = "landing" | "console" | "evidence" | "operations";

function viewFromHash(): View {
  const route = window.location.hash.replace(/^#\/?/, "");
  return route === "console" || route === "evidence" || route === "operations" ? route : "landing";
}

export function App() {
  const [view, setView] = useState<View>(viewFromHash);
  const [autoAct, setAutoAct] = useState<ActId | undefined>(undefined);

  useEffect(() => {
    const onHashChange = () => setView(viewFromHash());
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  useEffect(() => {
    document.body.classList.toggle("view-landing", view === "landing");
    document.body.classList.toggle("view-console", view === "console");
    document.body.classList.toggle("view-enterprise", view === "evidence" || view === "operations");
    return () => {
      document.body.classList.remove("view-landing", "view-console", "view-enterprise");
    };
  }, [view]);

  function navigate(next: View) {
    setAutoAct(undefined);
    window.location.hash = next === "landing" ? "" : `/${next}`;
    setView(next);
    window.scrollTo(0, 0);
  }

  function openConsole(act?: ActId) {
    setAutoAct(act);
    window.location.hash = "/console";
    setView("console");
    window.scrollTo(0, 0);
  }

  function backToProduct() {
    navigate("landing");
  }

  return (
    <div className="shell">
      {view === "landing" ? (
        <Landing
          onOpenConsole={() => openConsole()}
          onRunDemo={() => openConsole(1)}
          onNavigate={navigate}
        />
      ) : view === "console" ? (
        <Console key={autoAct ?? "manual"} onBack={backToProduct} onNavigate={navigate} autoAct={autoAct} />
      ) : view === "evidence" ? (
        <EvidenceRoom navigate={navigate} />
      ) : (
        <Operations navigate={navigate} />
      )}
    </div>
  );
}
