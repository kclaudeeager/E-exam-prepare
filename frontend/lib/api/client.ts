/**
 * Axios HTTP client with auth interceptors and error handling.
 */

import axios, { AxiosError, AxiosInstance } from 'axios';
import { API_URL, ACCESS_TOKEN_KEY } from '@/config/constants';

class APIClient {
  private instance: AxiosInstance;

  constructor() {
    this.instance = axios.create({
      baseURL: API_URL,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // ── Request Interceptor ────────────────────────────────────────────
    this.instance.interceptors.request.use(
      (config) => {
        const token = this.getToken();
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => Promise.reject(error),
    );

    // ── Response Interceptor ────────────────────────────────────────────
    this.instance.interceptors.response.use(
      (response) => response,
      async (error: AxiosError) => {
        // 401 Unauthorized → clear token and redirect to login
        if (error.response?.status === 401) {
          this.clearToken();
          window.location.href = '/login';
        }
        return Promise.reject(error);
      },
    );
  }

  // ── Token Management ──────────────────────────────────────────────────

  private getToken(): string | null {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem(ACCESS_TOKEN_KEY);
  }

  setToken(token: string): void {
    if (typeof window !== 'undefined') {
      localStorage.setItem(ACCESS_TOKEN_KEY, token);
    }
  }

  clearToken(): void {
    if (typeof window !== 'undefined') {
      localStorage.removeItem(ACCESS_TOKEN_KEY);
    }
  }

  // ── HTTP Methods ──────────────────────────────────────────────────────

  get<T>(url: string, config?: any) {
    return this.instance.get<T>(url, config);
  }

  post<T>(url: string, data?: any, config?: any) {
    return this.instance.post<T>(url, data, config);
  }

  put<T>(url: string, data?: any, config?: any) {
    return this.instance.put<T>(url, data, config);
  }

  patch<T>(url: string, data?: any, config?: any) {
    return this.instance.patch<T>(url, data, config);
  }

  delete<T>(url: string, config?: any) {
    return this.instance.delete<T>(url, config);
  }

  // ── FormData (for file uploads) ────────────────────────────────────────

  postFormData<T>(url: string, formData: FormData, config?: any) {
    return this.instance.post<T>(url, formData, {
      ...config,
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
  }
}

// Export singleton instance
export const apiClient = new APIClient();
