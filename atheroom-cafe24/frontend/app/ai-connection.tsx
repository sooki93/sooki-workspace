'use client';
import {useState} from 'react';
import type {Me} from './types';

export default function AIConnection({me}:{me:Me}) {
 const [message,setMessage]=useState(''),[checking,setChecking]=useState(false);
 const codex=me.ai_provider==='codex';
 async function check(){
  setChecking(true);
  try{
   const response=await fetch('/api/ai/status',{credentials:'same-origin'});
   const result=await response.json();
   setMessage(response.ok?result.message:'로그인 상태를 확인하고 다시 시도해주세요.');
  }catch{setMessage('작업실 연결을 확인하고 다시 시도해주세요.');}
  finally{setChecking(false);}
 }
 return <section className="card settings-wide">
  <h2>{codex?'Codex 구독으로 초안 작성':'AI 초안 작성'}</h2>
  <p>{codex?'연결된 맥북에 로그인된 ChatGPT 계정으로 사진을 분석하고 상품 설명을 만듭니다. API로 자동 전환하지 않습니다.':'OpenAI API를 사용합니다. API 사용료가 별도로 발생합니다.'}</p>
  {me.demo&&<p className="minor">{me.demo_ai_enabled?'사진 분석과 초안 작성은 실제 AI를 사용합니다. 쇼핑몰 연결과 상품 등록은 체험 상태입니다.':'현재 체험 초안은 AI를 호출하지 않습니다.'}</p>}
  {codex&&<p className="minor">사용 한도나 로그인 문제로 멈추면 작업을 보관합니다. 문제가 해결된 뒤 상품 화면에서 “다시 시작”을 누르세요. 맥이 켜져 있어야 처리할 수 있습니다.</p>}
  <button className="secondary" disabled={checking} onClick={check}>{checking?'확인 중…':'AI 연결 확인'}</button>
  {message&&<p className="info" role="status">{message}</p>}
 </section>;
}
