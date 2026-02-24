import axios from 'axios';

function resolveBaseURL(): string {
  const url = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
  if (import.meta.env.PROD && (url.includes('localhost') || url.includes('127.0.0.1'))) {
    throw new Error(
      'VITE_API_BASE_URL is localhost in a production build. ' +
      'Set the correct backend URL in Netlify → Environment variables and re-deploy.',
    );
  }
  return url;
}

const api = axios.create({
  baseURL: resolveBaseURL(),
  headers: { 'Content-Type': 'application/json' },
});

export default api;
