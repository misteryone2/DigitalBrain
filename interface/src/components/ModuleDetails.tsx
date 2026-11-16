
import type { BrainModule } from "../data/brainModules";

interface ModuleDetailsProps {
  module: BrainModule | null;
}

function ModuleDetails({ module }: ModuleDetailsProps) {
  if (!module) {
    return (
      <article className="panel module-details">
        <span className="panel-label">MODULE INSPECTOR</span>
        <h2>No module selected</h2>
        <p>Select a module in the 3D architecture to inspect its details.</p>
      </article>
    );
  }

  return (
    <article className="panel module-details">
      <span className="panel-label">MODULE INSPECTOR</span>

      <div className="module-details-heading">
        <span
          className="module-color"
          style={{ backgroundColor: `#${module.color.toString(16).padStart(6, "0")}` }}
        />

        <h2>{module.label}</h2>
      </div>

      <p>{module.description}</p>

      <div className="metric">
        <span>Module ID</span>
        <strong>{module.id}</strong>
      </div>

      <div className="metric">
        <span>Implementation</span>
        <strong>NOT IMPLEMENTED</strong>
      </div>

      <div className="metric">
        <span>Operational status</span>
        <strong>NOT AVAILABLE</strong>
      </div>
    </article>
  );
}

export default ModuleDetails;
