/**
 * Client-side providers for SWR, Auth, Theme.
 */

'use client';

import { ReactNode } from 'react';
import { SWRConfig } from 'swr';
import { apiClient } from '@/lib/api/client';

interface ProvidersProps {
  children: ReactNode;
}

const fetcher = async (url: string) => {
  const response = await apiClient.get(url);
  return response.data;
};

export function Providers({ children }: ProvidersProps) {
  return (
    <SWRConfig
      value={{
        fetcher,
        revalidateOnFocus: false,
        revalidateOnReconnect: true,
        dedupingInterval: 60000,
        focusThrottleInterval: 300000,
      }}
    >
      {children}
    </SWRConfig>
  );
}
