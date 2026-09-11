import {NextRequest, NextResponse} from 'next/server';

// External rewrite streams uploads to the Mac instead of a Vercel API function.
// The bridge credential is server-only and is never a response header.
export function proxy(request:NextRequest) {
 const backend=process.env.BACKEND_URL;
 const token=process.env.STUDIO_BRIDGE_TOKEN;
 if(process.env.VERCEL && (!backend || !token)) {
  return NextResponse.json({detail:'맥북 작업 도우미 연결이 준비되지 않았습니다.'},{status:503});
 }
 const destination=new URL(backend || 'http://127.0.0.1:8000');
 destination.pathname=request.nextUrl.pathname;
 destination.search=request.nextUrl.search;
 const headers=new Headers(request.headers);
 headers.delete('x-studio-bridge');
 if(token)headers.set('x-studio-bridge',token);
 const response=NextResponse.rewrite(destination,{request:{headers}});
 response.headers.set('Cache-Control','no-store');
 return response;
}

export const config={matcher:'/api/:path*'};
