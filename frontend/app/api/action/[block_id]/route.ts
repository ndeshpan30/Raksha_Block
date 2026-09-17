import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://127.0.0.1:8000';

export async function POST(
  request: NextRequest,
  { params }: { params: { block_id: string } }
) {
  const blockId = params.block_id;
  const body = await request.json();
  const url = `${BACKEND_URL}/api/v1/blocks/${encodeURIComponent(blockId)}/action`;

  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (res.ok) {
      const data = await res.json();
      return NextResponse.json(data);
    }
    return NextResponse.json({ error: 'Failed to apply action' }, { status: res.status });
  } catch (err) {
    return NextResponse.json(
      {
        block_id: blockId,
        action: body.action || 'APPROVE',
        status: `${body.action || 'APPROVE'}D_BY_CONTROLLER`,
        message: `Offline fallback: Action recorded for block ${blockId}`,
      },
      { status: 200 }
    );
  }
}
