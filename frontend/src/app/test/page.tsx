'use client';

import { useQuery } from '@tanstack/react-query';
import { getListings } from '@/lib/api';

export default function TestPage() {
  const { data: listings, isLoading, isError, error } = useQuery({
    queryKey: ['listings'],
    queryFn: getListings,
  });

  if (isLoading) {
    return <div>Loading listings...</div>;
  }

  if (isError) {
    return <div>Error fetching listings: {error.message}</div>;
  }

  return (
    <div style={{ fontFamily: 'monospace', padding: '2rem' }}>
      <h1>ReAgent API Connection Test</h1>
      <p>Successfully fetched data from the backend API.</p>
      <h2>Listings:</h2>
      <pre>{JSON.stringify(listings, null, 2)}</pre>
    </div>
  );
}