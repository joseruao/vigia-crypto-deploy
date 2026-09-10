import { NextResponse } from 'next/server';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'https://vigia-api.azurewebsites.net';

export async function GET() {
  try {
    // Usa o backend API em vez de Supabase diretamente
    const res = await fetch(`${API_BASE}/alerts/holdings`, {
      cache: 'no-store',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!res.ok) {
      console.error(`Backend API error: ${res.status} ${res.statusText}`);
      return NextResponse.json([], { status: res.status });
    }

    const data = await res.json();
    // Backend retorna array diretamente; aceita também { items: [...] }
    const items = Array.isArray(data) ? data : (data?.items || []);
    
    console.log(`📊 API Holdings: ${items.length} holdings encontrados`);
    return NextResponse.json(items);
  } catch (error) {
    console.error('Error fetching holdings:', error);
    return NextResponse.json([], { status: 500 });
  }
}