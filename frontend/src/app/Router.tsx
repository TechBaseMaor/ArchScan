import { createBrowserRouter, RouterProvider } from 'react-router-dom';
import Layout from './Layout';
import SimpleWorkflowPage from '../features/workflow/SimpleWorkflowPage';
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
      // Simple workflow — default
      { path: '/', element: <SimpleWorkflowPage /> },

      // Advanced mode routes
      { path: '/advanced', element: <ProjectsPage /> },
      { path: '/advanced/projects/:projectId', element: <ProjectDetailPage /> },
      { path: '/advanced/projects/:projectId/revisions/:revisionId/insights', element: <RevisionInsightsPage /> },
      { path: '/advanced/projects/:projectId/validate', element: <ValidationWizard /> },
      { path: '/advanced/validations/:validationId/findings', element: <FindingsPage /> },
      { path: '/rulesets', element: <RulesetsPage /> },
      { path: '/rulesets/:rulesetId', element: <RulesetDetailPage /> },
      { path: '/advanced/benchmarks', element: <BenchmarksPage /> },
      { path: '/advanced/benchmarks/:benchmarkId', element: <BenchmarkDetailPage /> },
      { path: '/advanced/reports/pilot-alon', element: <PilotAlonReportPage /> },
      { path: '/advanced/reports/pilot-alon/:validationId', element: <PilotAlonReportPage /> },
      { path: '/advanced/reviews', element: <ReviewQueuePage /> },
    ],
  },
]);

export default function AppRouter() {
  return <RouterProvider router={router} />;
}
