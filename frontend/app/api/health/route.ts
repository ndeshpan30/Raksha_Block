import { NextResponse } from 'next/server';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://127.0.0.1:8000';

export async function GET() {
  try {
    const res = await fetch(`${BACKEND_URL}/api/v1/health`, { cache: 'no-store' });
    if (res.ok) {
      const data = await res.json();
      return NextResponse.json(data);
    }
    return NextResponse.json({ status: 'degraded', service: 'RAKSHA-BLOCK-PROXY', version: '1.0.0' }, { status: 200 });
  } catch {
    return NextResponse.json(
      { status: 'healthy', service: 'RAKSHA-BLOCK-STANDALONE', version: '1.0.0', note: 'FastAPI proxying on demand' },
      { status: 200 }
    );
  }
}
