import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://127.0.0.1:8000';

export async function GET(
  request: NextRequest,
  { params }: { params: { block_id: string } }
) {
  const blockId = params.block_id;
  const url = `${BACKEND_URL}/api/v1/blocks/${encodeURIComponent(blockId)}/explain`;

  try {
    const res = await fetch(url, { cache: 'no-store' });
    if (res.ok) {
      const data = await res.json();
      return NextResponse.json(data);
    }
    return NextResponse.json({ error: 'Explanation not found' }, { status: res.status });
  } catch (err) {
    return NextResponse.json(
      { error: 'Backend API currently offline at ' + BACKEND_URL },
      { status: 503 }
    );
  }
}
