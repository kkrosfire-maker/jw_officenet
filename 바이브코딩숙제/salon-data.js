/* 정원헤어살롱 공용 데이터 (모든 프로그램이 이 파일 하나를 같이 씁니다)
   - 디자이너 7명, 근무표(요일 기본 휴무 + 날짜별 수정), 매출(시술) 내역
   - 처음 열면 6개월치 가상 데이터를 자동으로 만들어 이 브라우저에 저장합니다. */
(function(){
  'use strict';
  var KEY='jw_salon_v2', VER=2;

  var MENU=[
    ['컷','주니어컷(남)',18000],['컷','주니어컷(여)',20000],
    ['컷','청소년컷(남)',20000],['컷','청소년컷(여)',22000],
    ['컷','스파&남성 컷',23500],['컷','스파&여성 컷',26200],
    ['펌','일반펌',72000],['펌','열펌',108000],
    ['염색','염색',72000],['염색','뿌리염색',49900]
  ];
  var EXTRAS=[['두피관리',50000],['탈모관리',60000],['드라이',15000],['샴푸',10000]];
  function price(name){ for(var i=0;i<MENU.length;i++) if(MENU[i][1]===name) return MENU[i][2]; return 0; }

  var REG=['김하늘','이바다','박구름','최노을','정바람','한소라','오세아','강민서','윤서진','임도윤',
           '송지안','배서현','조하린','홍예준','문가온','신다온','권유진','황채원','안시우','류하준'];
  var SUR=['김','이','박','최','정','강','조','윤','장','임','한','오','서','신','권','황','안','송','전','홍'];
  var GIV=['서윤','민준','지우','하윤','도현','서연','예은','시우','주원','수아','지호','다인','유찬','채은','현우','나윤','은서','준서','가은','태양',
           '지안','소율','재민','윤아','건우','하은','승현','아라','동현','세린'];

  /* ---------- 날짜 도구 ---------- */
  function pad(n){ return n<10?'0'+n:''+n; }
  function ymd(d){ return d.getFullYear()+'-'+pad(d.getMonth()+1)+'-'+pad(d.getDate()); }
  function parse(s){ var p=s.split('-'); return new Date(+p[0],p[1]-1,+p[2]); }
  function addDays(d,n){ return new Date(d.getFullYear(),d.getMonth(),d.getDate()+n); }
  function today(){ var t=new Date(); return new Date(t.getFullYear(),t.getMonth(),t.getDate()); }
  function rng(seed){ return function(){ seed|=0; seed=seed+0x6D2B79F5|0; var t=Math.imul(seed^seed>>>15,1|seed);
    t=t+Math.imul(t^t>>>7,61|t)^t; return ((t^t>>>14)>>>0)/4294967296; }; }

  /* ---------- 가상 데이터 만들기 ---------- */
  function generate(){
    var R=rng(20261125);
    var ri=function(a,b){ return a+Math.floor(R()*(b-a+1)); };
    var pick=function(a){ return a[Math.floor(R()*a.length)]; };
    var shuffle=function(a){ a=a.slice(); for(var i=a.length-1;i>0;i--){ var j=Math.floor(R()*(i+1)); var t=a[i]; a[i]=a[j]; a[j]=t; } return a; };

    var td=today(), start=new Date(td.getFullYear(),td.getMonth()-5,1);   // 6개월 전 1일 ~ 오늘
    var days=Math.round((td-start)/86400000)+1;

    var store={ver:VER,
      designers:[ {name:'정원',role:'원장',off:[1,2]}, {name:'유나',role:'부원장',off:[1,3]},
                  {name:'지수',role:'디자이너',off:[2,4]}, {name:'민호',role:'디자이너',off:[3,5]},
                  {name:'서연',role:'디자이너',off:[4,0]}, {name:'하준',role:'디자이너',off:[5,0]},
                  {name:'다은',role:'디자이너',off:[3,6]} ],
      roster:{}, sales:[]};

    function working(date){
      var wd=parse(date).getDay();
      return store.designers.filter(function(d){ return d.off.indexOf(wd)<0; }).map(function(d){ return d.name; });
    }

    // 단골 20명: 주니어 3, 청소년 2, 성인 15. 주니어는 염색 안 함, 나머지(17명) 중 12명(약 60%)이 염색
    var dyeIdx=shuffle(Array.apply(null,Array(17)).map(function(_,i){return i+3;})).slice(0,12);
    var regs=REG.map(function(n,i){
      return {name:n, age:i<3?'주니어':(i<5?'청소년':'성인'), g:(i%3===0)?'남':'여', dye:dyeIdx.indexOf(i)>=0,
              des:store.designers[ri(0,6)].name};
    });
    regs[2].g='남'; regs[0].g='여'; regs[1].g='여';

    // 단골 방문일 (컷 2개월, 펌 3개월 주기, 염색은 컷과 같이)
    var dayVisits=[]; for(var i=0;i<days+12;i++) dayVisits.push([]);
    regs.forEach(function(c){
      var visits=[], d;
      for(d=ri(0,59); d<days; d+=60+ri(-3,3)) visits.push({idx:d,cust:c,svcs:['cut'].concat(c.dye?['dye']:[])});
      for(d=ri(0,89); d<days; d+=90+ri(-4,4)){
        var near=visits.filter(function(v){ return Math.abs(v.idx-d)<=5 && v.svcs.indexOf('cut')>=0; })[0];
        if(near) near.svcs.push('perm'); else visits.push({idx:d,cust:c,svcs:['perm']});
      }
      visits.forEach(function(v){ dayVisits[v.idx].push(v); });
    });
    for(i=0;i<days;i++) while(dayVisits[i].length>10) dayVisits[i+1].push(dayVisits[i].pop());

    // 일반 손님 이름 풀 (단골과 겹치지 않게 60명)
    var pool=[]; var seen={}; REG.forEach(function(n){seen[n]=1;});
    while(pool.length<60){ var nm=pick(SUR)+pick(GIV); if(!seen[nm]){ seen[nm]=1; pool.push(nm); } }

    function cutName(age,g){ return age==='주니어'?'주니어컷('+g+')':age==='청소년'?'청소년컷('+g+')':'스파&'+(g==='남'?'남성':'여성')+' 컷'; }
    var vseq=0, byDate={};
    for(i=0;i<days;i++){
      var date=ymd(addDays(start,i)), list=dayVisits[i].slice(), target=ri(5,10);
      while(list.length<target){            // 모자란 건수는 일반 손님으로
        var ar=R(), age=ar<.15?'주니어':ar<.25?'청소년':'성인', g=R()<.4?'남':'여', roll=R(), s;
        if(roll<.50) s=['cut']; else if(roll<.70) s=['perm']; else if(roll<.85) s=['dye']; else s=['cut','dye'];
        if(age==='주니어') s=s.filter(function(x){return x!=='dye';});   // 주니어는 염색 안 함
        if(!s.length) s=['cut'];
        list.push({cust:{name:pick(pool),age:age,g:g,des:null},svcs:s});
      }
      var work=working(date), recs=[];
      list.forEach(function(v){
        var c=v.cust, des=(c.des&&work.indexOf(c.des)>=0)?c.des:pick(work), rate=R()<.15?10:0, vid='v'+(++vseq);
        v.svcs.forEach(function(k){
          var nm= k==='cut'?cutName(c.age,c.g) : k==='perm'?(R()<.65?'일반펌':'열펌') : (R()<.6?'염색':'뿌리염색');
          var p=price(nm), pay=p-Math.floor(p*rate/100);
          store.sales.push({id:'s'+store.sales.length,v:vid,date:date,des:des,cust:c.name,name:nm,price:p,qty:1,rate:rate,pay:pay});
        });
        recs.push(vid);
      });
      byDate[date]=recs;
    }

    // 직접입력 항목(두피관리·탈모관리·드라이·샴푸): 각각 월 1건
    var months={}; Object.keys(byDate).forEach(function(d){ (months[d.slice(0,7)]=months[d.slice(0,7)]||[]).push(d); });
    Object.keys(months).forEach(function(m){
      EXTRAS.forEach(function(e){
        var d=pick(months[m]), vid=pick(byDate[d]);
        var base=store.sales.filter(function(s){return s.v===vid;})[0];
        store.sales.push({id:'s'+store.sales.length,v:vid,date:d,des:base.des,cust:base.cust,name:e[0],price:e[1],qty:1,rate:0,pay:e[1]});
      });
    });
    store.sales.sort(function(a,b){ return a.date<b.date?-1:a.date>b.date?1:0; });
    return store;
  }

  /* ---------- 저장소 ---------- */
  var store=null;
  function save(){ try{ localStorage.setItem(KEY,JSON.stringify(store)); }catch(e){} }
  function load(){
    if(store) return store;
    try{ store=JSON.parse(localStorage.getItem(KEY)); }catch(e){ store=null; }
    if(!store||store.ver!==VER){ store=generate(); save(); }
    return store;
  }
  function fresh(){ store=null; return load(); }          // 다른 화면에서 바꾼 내용 다시 읽기

  var Salon={
    MENU:MENU, EXTRAS:EXTRAS, ymd:ymd, parse:parse, today:today, addDays:addDays,
    reload:fresh,
    reset:function(){ store=generate(); save(); },
    designers:function(){ return fresh().designers; },
    roleOf:function(n){ var d=load().designers.filter(function(x){return x.name===n;})[0]; return d?d.role:''; },
    addDesigner:function(name,role){ var s=fresh(); s.designers.push({name:name,role:role||'디자이너',off:[0]}); save(); },
    removeDesigner:function(name){ var s=fresh(); s.designers=s.designers.filter(function(d){return d.name!==name;}); save(); },
    isOff:function(date,name){
      var s=load(), k=date+'|'+name;
      if(k in s.roster) return !!s.roster[k];
      var d=s.designers.filter(function(x){return x.name===name;})[0];
      return d?d.off.indexOf(parse(date).getDay())>=0:true;
    },
    setOff:function(date,name,off){
      var s=fresh(), d=s.designers.filter(function(x){return x.name===name;})[0]; if(!d) return;
      var def=d.off.indexOf(parse(date).getDay())>=0, k=date+'|'+name;
      if(off===def) delete s.roster[k]; else s.roster[k]=off?1:0;
      save();
    },
    working:function(date){ fresh(); return Salon.designers().filter(function(d){ return !Salon.isOff(date,d.name); }).map(function(d){return d.name;}); },
    sales:function(){ return fresh().sales; },
    addVisit:function(v){
      var s=fresh(), vid='v'+Date.now();
      v.items.forEach(function(it,i){
        s.sales.push({id:'s'+Date.now()+'_'+i,v:vid,date:v.date,des:v.des,cust:v.cust,name:it.name,price:it.price,qty:it.qty,rate:it.rate,pay:it.pay});
      });
      save(); return vid;
    },
    removeVisit:function(vid){ var s=fresh(); s.sales=s.sales.filter(function(x){return x.v!==vid;}); save(); },
    // 방문 단위로 묶기 → [{v,date,des,cust,items:[],total}]
    visits:function(from,to){
      var m={}, out=[];
      Salon.sales().forEach(function(x){
        if((from&&x.date<from)||(to&&x.date>to)) return;
        var o=m[x.v]; if(!o){ o=m[x.v]={v:x.v,date:x.date,des:x.des,cust:x.cust,items:[],total:0}; out.push(o); }
        o.items.push(x); o.total+=x.pay;
      });
      return out;
    },
    // 기간 내 방문 손님 이름 집계 → [{name,n}] (방문 많은 순)
    customers:function(from,to){
      var c={}; Salon.visits(from,to).forEach(function(v){ c[v.cust]=(c[v.cust]||0)+1; });
      return Object.keys(c).map(function(k){return {name:k,n:c[k]};}).sort(function(a,b){ return b.n-a.n||(a.name<b.name?-1:1); });
    }
  };
  window.Salon=Salon;
})();
