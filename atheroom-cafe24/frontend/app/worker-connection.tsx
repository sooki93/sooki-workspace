'use client';
import {useEffect, useState} from 'react';

type Status = {enabled:boolean, online?:boolean, ready?:boolean, message?:string, queued?:number, waiting?:number};

export default function WorkerConnection() {
 const [status,setStatus]=useState<Status|null>(null);
 const [unreachable,setUnreachable]=useState(false);
 useEffect(()=>{
  let disposed=false;
  const controller=new AbortController();
  async function refresh(){
   try {
    const response=await fetch('/api/worker/status',{credentials:'same-origin',cache:'no-store',signal:controller.signal});
    if(!response.ok)throw new Error('connection');
    const data:Status=await response.json();
    if(!disposed){setStatus(data);setUnreachable(false);}
   }catch{if(!disposed)setUnreachable(true);}
  }
  void refresh();
  const timer=setInterval(()=>void refresh(),15000);
  return()=>{disposed=true;controller.abort();clearInterval(timer);};
 },[]);
 if(unreachable)return <div className="info" role="status">작업실 연결을 확인하고 있습니다. 연결이 복구되면 저장 여부와 진행 상태를 다시 확인해주세요.</div>;
 if(!status?.enabled)return null;
 return <div className="info" role="status">
  <strong>{status.online?'맥북 연결됨':'맥북 연결 대기'}</strong><br/>{status.message}
  {!!status.queued&&<span> · 대기 요청 {status.queued}건</span>}
  {!!status.waiting&&<p>AI 확인이 필요한 작업 {status.waiting}건이 있습니다. 로그인 또는 사용 한도 문제가 해결되면 해당 작업에서 다시 시작을 눌러주세요.</p>}
 </div>;
}
