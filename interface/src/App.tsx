
import { useState } from "react";
import Brain from "./components/Brain";
import ModuleDetails from "./components/ModuleDetails";
import { brainModules } from "./data/brainModules";

function App() {
  const [selectedModuleId, setSelectedModuleId] = useState<string | null>(
    null
  );

  const selectedModule =
    brainModules.find((module) => module.id === selectedModuleId) ?? null;

  return (
    <main className="dashboard">
      <header className="topbar">
        <div>
          <h1>DigitalBrain</h1>
          <span>COGNITIVE SYSTEM CONTROL CENTER</span>
        </div>

        <div className="system-status">
          <span className="status-dot"></span>
          INITIALIZING
        </div>
      </header>

      <section className="overview">
        <article className="panel core-panel">
          <span className="panel-label">CORE SYSTEM</span>
          <h2>Digital Brain</h2>
          <p>Central cognitive architecture</p>

          <div className="core-visual">
            <Brain
              onSelectModule={setSelectedModuleId}
              selectedModuleId={selectedModuleId}
            />
          </div>

          <span className="demo-label">
            3D VISUALIZATION — DEVELOPMENT PREVIEW
          </span>
        </article>

        <ModuleDetails module={selectedModule} />

        <article className="panel metrics-panel">
          <span className="panel-label">SYSTEM OVERVIEW</span>
          <h2>Architecture status</h2>

          <div className="metric">
            <span>Core</span>
            <strong>INITIALIZING</strong>
          </div>

          <div className="metric">
            <span>Memory</span>
            <strong>NOT CONNECTED</strong>
          </div>

          <div className="metric">
            <span>Reasoning</span>
            <strong>NOT AVAILABLE</strong>
          </div>

          <div className="metric">
            <span>Evolution</span>
            <strong>NOT AVAILABLE</strong>
          </div>
        </article>
      </section>

      <section className="modules-section">
        <div className="section-heading">
          <h2>Cognitive modules</h2>
          <span>ARCHITECTURE PREVIEW</span>
        </div>

        <div className="module-grid">
          {brainModules.map((module) => (
            <article
              className={`module-card ${
  selectedModuleId === module.id ? "selected" : ""
}`}
              key={module.id}
              onClick={() => setSelectedModuleId(module.id)}
              role="button"
              tabIndex={0}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  setSelectedModuleId(module.id);
                }
              }}
            >
              <span className="module-indicator"></span>
              <h3>{module.label}</h3>
              <p>{module.description}</p>
            </article>
          ))}
        </div>
      </section>

      <footer>
        DIGITALBRAIN · DEVELOPMENT ENVIRONMENT · DEMO DATA
      </footer>
    </main>
  );
}

export default App;
