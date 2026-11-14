import './protegerDom';import React from 'react';import{createRoot}from'react-dom/client';import App from './App';import './style.css';import{iniciarApp}from'./lib/app';iniciarApp();
// Celular aberto em "modo computador": a página fica larga, mas a tela física é pequena e o toque é de dedo.
try{ if(matchMedia('(pointer:coarse)').matches&&Math.min(screen.width,screen.height)<600&&innerWidth>820) document.documentElement.classList.add('celular'); }catch{ /* sem matchMedia */ }
createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
