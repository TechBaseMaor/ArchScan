import { createBrowserRouter, RouterProvider } from 'react-router-dom';
import Layout from './Layout';
import ProjectsPage from '../features/projects/ProjectsPage';
import ProjectDetailPage from '../features/projects/ProjectDetailPage';
import ValidationWizard from '../features/validations/ValidationWizard';
import FindingsPage from '../features/validations/FindingsPage';
import RulesetsPage from '../features/rulesets/RulesetsPage';
import RulesetDetailPage from '../features/rulesets/RulesetDetailPage';
import BenchmarksPage from '../features/benchmarks/BenchmarksPage';
import BenchmarkDetailPage from '../features/benchmarks/BenchmarkDetailPage';

const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { path: '/', element: <ProjectsPage /> },
      { path: '/projects/:projectId', element: <ProjectDetailPage /> },
      { path: '/projects/:projectId/validate', element: <ValidationWizard /> },
      { path: '/validations/:validationId/findings', element: <FindingsPage /> },
      { path: '/rulesets', element: <RulesetsPage /> },
      { path: '/rulesets/:rulesetId', element: <RulesetDetailPage /> },
      { path: '/benchmarks', element: <BenchmarksPage /> },
      { path: '/benchmarks/:benchmarkId', element: <BenchmarkDetailPage /> },
    ],
  },
]);

export default function AppRouter() {
  return <RouterProvider router={router} />;
}
