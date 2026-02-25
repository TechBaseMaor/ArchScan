import { createBrowserRouter, RouterProvider } from 'react-router-dom';
import Layout from './Layout';
import ProjectsPage from '../features/projects/ProjectsPage';
import ProjectDetailPage from '../features/projects/ProjectDetailPage';
import RevisionInsightsPage from '../features/projects/RevisionInsightsPage';
import ValidationWizard from '../features/validations/ValidationWizard';
import FindingsPage from '../features/validations/FindingsPage';
import RulesetsPage from '../features/rulesets/RulesetsPage';
import RulesetDetailPage from '../features/rulesets/RulesetDetailPage';
import BenchmarksPage from '../features/benchmarks/BenchmarksPage';
import BenchmarkDetailPage from '../features/benchmarks/BenchmarkDetailPage';
import PilotAlonReportPage from '../features/reports/PilotAlonReportPage';
import ReviewQueuePage from '../features/reviews/ReviewQueuePage';

const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { path: '/', element: <ProjectsPage /> },
      { path: '/projects/:projectId', element: <ProjectDetailPage /> },
      { path: '/projects/:projectId/revisions/:revisionId/insights', element: <RevisionInsightsPage /> },
      { path: '/projects/:projectId/validate', element: <ValidationWizard /> },
      { path: '/validations/:validationId/findings', element: <FindingsPage /> },
      { path: '/rulesets', element: <RulesetsPage /> },
      { path: '/rulesets/:rulesetId', element: <RulesetDetailPage /> },
      { path: '/benchmarks', element: <BenchmarksPage /> },
      { path: '/benchmarks/:benchmarkId', element: <BenchmarkDetailPage /> },
      { path: '/reports/pilot-alon', element: <PilotAlonReportPage /> },
      { path: '/reports/pilot-alon/:validationId', element: <PilotAlonReportPage /> },
      { path: '/reviews', element: <ReviewQueuePage /> },
    ],
  },
]);

export default function AppRouter() {
  return <RouterProvider router={router} />;
}
