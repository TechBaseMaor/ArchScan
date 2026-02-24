import axios, { AxiosError } from 'axios';

export function resolveBaseURL(): string {
  const url = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
  if (import.meta.env.PROD && (url.includes('localhost') || url.includes('127.0.0.1'))) {
    throw new Error(
      'VITE_API_BASE_URL is localhost in a production build. ' +
      'Set the correct backend URL in Netlify → Environment variables and re-deploy.',
    );
  }
  return url;
}

const REQUEST_TIMEOUT_MS = 15_000;

const api = axios.create({
  baseURL: resolveBaseURL(),
  headers: { 'Content-Type': 'application/json' },
  timeout: REQUEST_TIMEOUT_MS,
});

export class NetworkError extends Error {
  public isTimeout: boolean;
  constructor(message: string, isTimeout = false) {
    super(message);
    this.name = 'NetworkError';
    this.isTimeout = isTimeout;
  }
}

api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
      return Promise.reject(new NetworkError(
        'Server did not respond in time. It may be starting up — please try again in a moment.',
        true,
      ));
    }
    if (!error.response) {
      return Promise.reject(new NetworkError(
        'Cannot reach the server. Check your connection or try again shortly.',
      ));
    }
    return Promise.reject(error);
  },
);

export default api;
