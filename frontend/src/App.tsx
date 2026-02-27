import { NavLink, Route, Routes } from 'react-router-dom';
import ExperimentsPage from './pages/ExperimentsPage';
import ExperimentDetailPage from './pages/ExperimentDetailPage';
import AssetsPage from './pages/AssetsPage';
import RunMonitorPage from './pages/RunMonitorPage';
import ResultsPage from './pages/ResultsPage';
import ExportPage from './pages/ExportPage';

export default function App() {
  return (
    <div className="app">
      <nav className="sidebar">
        <h1>🧪 NBP Lab</h1>
        <NavLink to="/" end>
          Experiments
        </NavLink>
        <NavLink to="/assets">Assets &amp; QC</NavLink>
        <NavLink to="/monitor">Run Monitor</NavLink>
        <NavLink to="/results">Results</NavLink>
        <NavLink to="/export">Export</NavLink>
      </nav>

      <main className="main">
        <Routes>
          <Route path="/" element={<ExperimentsPage />} />
          <Route path="/experiments/:id" element={<ExperimentDetailPage />} />
          <Route path="/assets" element={<AssetsPage />} />
          <Route path="/monitor" element={<RunMonitorPage />} />
          <Route path="/results" element={<ResultsPage />} />
          <Route path="/export" element={<ExportPage />} />
        </Routes>
      </main>
    </div>
  );
}
