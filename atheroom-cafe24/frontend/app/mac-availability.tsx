'use client';
import {useEffect,useState} from 'react';

export default function MacAvailability(){
 const [offline,setOffline]=useState(false);
 useEffect(()=>{
  let disposed=false;
  async function check(){
   try {
    const response=await fetch('/api/public-settings',{cache:'no-store',signal:AbortSignal.timeout(10000)});
    if(!response.ok)throw new Error('offline');
    const body=await response.json();
    if(typeof body.demo!=='boolean')throw new Error('offline');
    if(!disposed)setOffline(false);
   }catch{if(!disposed)setOffline(true);}
  }
  void check();const timer=setInterval(()=>void check(),15000);
  return()=>{disposed=true;clearInterval(timer);};
 },[]);
 if(!offline)return null;
 return <div className="info" role="alert"><strong>맥북 작업실에 연결할 수 없습니다.</strong><p>맥북에서 “온라인 작업실 열기”를 실행하고 인터넷과 잠자기 상태를 확인해주세요. 연결이 복구되어야 사진 저장·상품 조회·AI 작업을 할 수 있습니다. 연결이 끊긴 동안 입력한 내용은 아직 저장되지 않았을 수 있습니다.</p><button className="secondary" onClick={()=>window.location.reload()}>다시 연결하기</button></div>;
}
