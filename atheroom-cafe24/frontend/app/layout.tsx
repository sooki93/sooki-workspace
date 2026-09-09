import type { Metadata } from 'next';
import './globals.css';
export const metadata:Metadata={title:'엣더룸 · 상품 작업실',description:'기존 쇼핑몰의 형식으로 새 상품을 준비하는 작업실'};
export default function Layout({children}:{children:React.ReactNode}){return <html lang="ko"><body>{children}</body></html>}
