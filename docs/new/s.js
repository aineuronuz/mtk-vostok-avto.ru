(()=>{
const $=s=>document.querySelector(s),$$=(s,r=document)=>[...r.querySelectorAll(s)];
const RM=matchMedia('(prefers-reduced-motion:reduce)').matches;
const mob=()=>innerWidth<=760;
const clamp=(v,a=0,b=1)=>Math.min(b,Math.max(a,v));
const nf=n=>String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g,' ');

// меню на телефоне
const bg=$('.burger');if(bg)bg.onclick=()=>document.body.classList.toggle('open');
$$('.drawer a').forEach(a=>a.addEventListener('click',()=>document.body.classList.remove('open')));

// плавный переход: фото карточки «перелетает» на страницу модели или машины
document.addEventListener('click',e=>{const a=e.target.closest('a[data-vt]');if(!a)return;
  $$('.mpic,.gmain').forEach(x=>x.style.viewTransitionName='none');const im=a.querySelector('img');if(im)im.style.viewTransitionName='car'});
addEventListener('pageshow',()=>$$('a[data-vt] img').forEach(i=>i.style.viewTransitionName=''));

// появление
const io=new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting){e.target.classList.add('in');io.unobserve(e.target)}}),{rootMargin:'0px 0px -8% 0px'});
$$('.rv,.deck').forEach(e=>io.observe(e));
// счётчики
const co=new IntersectionObserver(es=>es.forEach(e=>{if(!e.isIntersecting)return;co.unobserve(e.target);const b=e.target,n=+b.dataset.n,f=+(b.dataset.from||0),t0=performance.now();
  const st=t=>{const p=clamp((t-t0)/1600),v=Math.round(f+(n-f)*(1-Math.pow(1-p,3)));b.textContent=v;if(p<1)requestAnimationFrame(st)};if(!RM)requestAnimationFrame(st)}),{threshold:.6});
$$('[data-n]').forEach(e=>co.observe(e));

// первый экран: смена фото
const sl=$$('.slides picture'),dt=$$('.dots i');
if(sl.length){let si=0;const show=i=>{sl.forEach((e,k)=>e.classList.toggle('on',k==i));dt.forEach((e,k)=>{e.classList.remove('on');if(k==i){void e.offsetWidth;e.classList.add('on')}})};
  show(0);if(!RM)setInterval(()=>{si=(si+1)%sl.length;show(si)},6000)}

// слова подсвечиваются
const W=$('#words');let ws=[];
if(W){W.innerHTML=W.innerHTML.split(/(\s+)/).map(t=>{if(/^\s+$/.test(t)||!t)return t;const k=t.includes('*');return `<span class="w${k?' k':''}">${t.replace(/\*/g,'')}</span>`}).join('');ws=$$('#words .w')}

// ленты со стрелками
$$('[data-reel]').forEach(b=>{const r=document.getElementById(b.dataset.reel);b.onclick=()=>r.scrollBy({left:+b.dataset.d*r.clientWidth*.8,behavior:'smooth'})});

// фильтры каталога и машин
const L=$('[data-list]');
if(L){
  const cards=$$('.card',L),cnt=$('#cnt'),emp=$('#empty'),sortSel=$('[data-sort]'),params=new URLSearchParams(location.search);
  const groups=$$('[data-f]');
  groups.forEach(g=>{const k=g.dataset.f,v=params.get(k);if(v==null)return;
    if(g.matches('.chips,.tiles'))v.split(',').forEach(x=>{const c=g.querySelector(`[data-v="${x}"]`);if(c)c.classList.add('on')});else g.value=v});
  if(sortSel&&params.get('sort'))sortSel.value=params.get('sort');
  const st=()=>{const s={};groups.forEach(g=>{const k=g.dataset.f;
      if(g.matches('.chips,.tiles')){const on=$$('.on',g).map(c=>c.dataset.v);if(on.length)s[k]=on}
      else if(g.type=='range'){if(+g.value<+g.max)s[k]=+g.value}
      else if(g.value!=='')s[k]=g.value});return s};
  const lbl=$$('[data-out]');
  const apply=(push=true)=>{const s=st();let n=0;
    lbl.forEach(o=>{const g=$(`[data-f="${o.dataset.out}"]`);o.textContent=+g.value>=+g.max?'любая':`до ${(+g.value/1e6).toFixed(1).replace('.',',')} млн ₽`});
    cards.forEach(c=>{const d=c.dataset;let ok=true;
      for(const k in s){const v=s[k];
        if(Array.isArray(v)){if(k=='feat'){if(!v.every(x=>(d.feat||'').split(' ').includes(x)))ok=false}else if(!v.some(x=>(d[k]||'').split(' ').includes(x)))ok=false}
        else if(k=='q'){if(!d.q.includes(v.trim().toLowerCase()))ok=false}
        else if(k=='price'){if(+d.price>v)ok=false}
        else if(k=='ymin'){if(+d.year<+v)ok=false}
        else if(k=='kmmax'){if(+d.km>+v)ok=false}
        else if((d[k]||'')!=v)ok=false;
        if(!ok)break}
      c.classList.toggle('x',!ok);if(ok){n++;if(!RM){c.style.animation='none';void c.offsetWidth;c.style.animation=''}}});
    if(sortSel){const m=sortSel.value,[f,dir]=m.split('-');const arr=cards.slice().sort((a,b)=>{const x=a.dataset[f],y=b.dataset[f];
        const r=isNaN(+x)?x.localeCompare(y,'ru'):(+x)-(+y);return dir=='desc'?-r:r});arr.forEach(c=>L.appendChild(c))}
    if(cnt)cnt.textContent=n;if(emp)emp.classList.toggle('on',n==0);
    if(push){const p=new URLSearchParams();for(const k in s)p.set(k,Array.isArray(s[k])?s[k].join(','):s[k]);if(sortSel&&sortSel.selectedIndex>0)p.set('sort',sortSel.value);
      history.replaceState(null,'',location.pathname+(p.toString()?'?'+p:''))}};
  groups.forEach(g=>{if(g.matches('.chips,.tiles'))g.addEventListener('click',e=>{const c=e.target.closest('[data-v]');if(!c)return;
      if(g.dataset.one!=null)$$('[data-v]',g).forEach(x=>{if(x!=c)x.classList.remove('on')});c.classList.toggle('on');apply()});
    else g.addEventListener('input',()=>apply())});
  if(sortSel)sortSel.addEventListener('change',()=>apply());
  $$('[data-reset]').forEach(b=>b.onclick=()=>{groups.forEach(g=>{if(g.matches('.chips,.tiles'))$$('.on',g).forEach(c=>c.classList.remove('on'));else if(g.type=='range')g.value=g.max;else g.value=''});apply()});
  $$('[data-fopen]').forEach(b=>b.onclick=()=>document.body.classList.toggle('fopen'));
  apply(false);
}

// галерея машины
const G=$('.gmain');
if(G){const ims=$$('img',G),th=$$('.gth img'),gn=$('.gn',G),lb=$('.lbox'),li=lb&&$('img',lb);let i=0;
  const go=k=>{i=(k+ims.length)%ims.length;ims.forEach((e,j)=>{e.classList.toggle('on',j==i);if(j==i&&e.dataset.src){e.src=e.dataset.src;delete e.dataset.src}});
    th.forEach((e,j)=>e.classList.toggle('on',j==i));if(gn)gn.textContent=`${i+1} / ${ims.length}`;if(li&&lb.classList.contains('on'))li.src=ims[i].dataset.big||ims[i].src;
    const n=ims[(i+1)%ims.length];if(n.dataset.src){n.src=n.dataset.src;delete n.dataset.src}};
  th.forEach((e,j)=>e.onclick=()=>go(j));
  $('.pv',G).onclick=e=>{e.stopPropagation();go(i-1)};$('.nx',G).onclick=e=>{e.stopPropagation();go(i+1)};
  let x0=null;G.addEventListener('touchstart',e=>x0=e.touches[0].clientX,{passive:true});
  G.addEventListener('touchend',e=>{if(x0==null)return;const dx=e.changedTouches[0].clientX-x0;if(Math.abs(dx)>40)go(i+(dx<0?1:-1));x0=null});
  if(lb){G.addEventListener('click',()=>{lb.classList.add('on');li.src=ims[i].dataset.big||ims[i].src});
    $('.x',lb).onclick=()=>lb.classList.remove('on');$('.pv',lb).onclick=()=>go(i-1);$('.nx',lb).onclick=()=>go(i+1);
    lb.addEventListener('click',e=>{if(e.target==lb)lb.classList.remove('on')});
    addEventListener('keydown',e=>{if(!lb.classList.contains('on'))return;if(e.key=='Escape')lb.classList.remove('on');if(e.key=='ArrowLeft')go(i-1);if(e.key=='ArrowRight')go(i+1)})}
  go(0)}

// прокрутка
const hdr=$('#hdr'),top0=$('.hero,.phead,.mhero'),hc=$('#hc'),fr=$('#fr'),grow=$('#grow'),how=$('#how'),track=$('#track'),prog=$('#prog'),pays=$('#pays'),fin=$('#finbg'),tl=$('.tl');
let lastY=scrollY,ticking=false;
function frame(){
  ticking=false;const y=scrollY,vh=innerHeight,vw=innerWidth;
  const past=y>(top0?top0.offsetHeight-90:0);hdr.classList.toggle('solid',past);
  hdr.classList.toggle('hide',past&&y>lastY+4&&y>vh*1.5&&!document.body.classList.contains('open'));
  if(y<lastY-4)hdr.classList.remove('hide');lastY=y;
  if(RM)return;
  if(hc&&y<vh*1.2){const p=clamp(y/vh);hc.style.transform=mob()?`translateY(${p*-50}px)`:`translateY(calc(-42% - ${p*80}px))`;hc.style.opacity=mob()?1-p*.9:1-p*1.3}
  if(ws.length){const r=W.getBoundingClientRect(),wp=clamp((vh*.86-r.top)/(r.height+vh*.36)),nOn=Math.round(wp*ws.length*1.08);ws.forEach((w,i)=>w.classList.toggle('on',i<nOn))}
  if(grow&&!mob()){const g=grow.getBoundingClientRect(),gp=clamp(-g.top/(g.height-vh)),e=clamp(gp/.6);
    fr.style.width=`${60+40*e}vw`;fr.style.height=`${62+38*e}vh`;fr.style.borderRadius=`${28*(1-e)}px`;fr.style.setProperty('--o',clamp((gp-.45)/.3))}
  if(how&&track){if(!mob()){const h=how.getBoundingClientRect(),dist=track.scrollWidth-vw;how.style.height=`${dist+vh}px`;
    const hp=clamp(-h.top/(how.offsetHeight-vh));track.style.transform=`translateX(${-hp*dist}px)`;if(prog)prog.style.setProperty('--p',hp)}else how.style.height=''}
  if(pays){const pr=pays.getBoundingClientRect(),pp=clamp((vh*.8-pr.top)/(vh*.55));pays.style.setProperty('--p',pp);$$('.pay4',pays).forEach((e,i)=>e.classList.toggle('on',pp>=i/3-.01&&pp>0))}
  if(tl){const r=tl.getBoundingClientRect(),h=clamp(vh*.6-r.top,0,r.height-40);tl.style.setProperty('--h',h+'px');$$('.ts',tl).forEach(s=>s.classList.toggle('on',s.getBoundingClientRect().top+40<vh*.6))}
  $$('.dc').forEach(d=>{const b=d.getBoundingClientRect();if(b.bottom<0||b.top>vh)return;const q=(b.top+b.height/2-vh/2)/vh;$$('img',d).forEach(im=>im.style.transform=`translateY(${q*-6}%)`)});
  if(fin){const fb=fin.getBoundingClientRect();if(fb.top<vh&&fb.bottom>0)fin.style.transform=`translateY(${(fb.top/vh)*-8}%)`}
}
const req=()=>{if(!ticking){ticking=true;requestAnimationFrame(frame)}};
addEventListener('scroll',req,{passive:true});addEventListener('resize',req);addEventListener('load',req);frame();
if(!RM&&$('.dc'))setInterval(()=>$$('.dc').forEach((d,i)=>setTimeout(()=>d.classList.toggle('alt'),i*500)),4200);
})();
