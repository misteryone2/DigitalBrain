
function App() {
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
            <div className="core-orbit">
              <div className="core-center">DB</div>
            </div>
          </div>
          <span className="demo-label">VISUAL PREVIEW — DEMO</span>
        </article>

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
          {[
            "INPUT",
            "MEMORY",
            "KNOWLEDGE",
            "REASONING",
            "PLANNING",
            "LEARNING",
            "METACOGNITION",
            "EXECUTION",
            "EVOLUTION",
            "VALIDATION",
          ].map((module) => (
            <article className="module-card" key={module}>
              <span className="module-indicator"></span>
              <h3>{module}</h3>
              <p>Awaiting implementation</p>
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

