import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://127.0.0.1:8000';

export async function POST(request: NextRequest) {
  let body = {};
  try {
    body = await request.json();
  } catch {
    body = {};
  }

  const { searchParams } = new URL(request.url);
  const queryString = searchParams.toString();
  const url = `${BACKEND_URL}/optimize${queryString ? `?${queryString}` : ''}`;

  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      cache: 'no-store',
    });
    if (res.ok) {
      const data = await res.json();
      return NextResponse.json(data);
    }
    return NextResponse.json({ error: 'Optimizer failed', status: res.status }, { status: res.status });
  } catch (err) {
    return NextResponse.json(
      { error: 'Backend API currently offline at ' + BACKEND_URL },
      { status: 503 }
    );
  }
}
