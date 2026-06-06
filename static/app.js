(function(){
 const brands=window.BRANDS||{};
 const brand=document.getElementById('brand');
 const model=document.getElementById('model');
 const trim=document.getElementById('trim');
 function fill(sel, arr){ if(!sel||!arr||!arr.length) return; const old=sel.value; sel.innerHTML=''; arr.forEach(v=>{const o=document.createElement('option'); o.value=v; o.textContent=v; sel.appendChild(o)}); if(arr.includes(old)) sel.value=old; }
 function update(){ const b=brand&&brand.value; if(brands[b]){ fill(model, brands[b].models); fill(trim, brands[b].packages); } }
 if(brand){ brand.addEventListener('change',update); update(); }
})();
