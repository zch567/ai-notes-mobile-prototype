export function Card({ title, subtitle, children, className = "" }) {
  return (
    <section className={`rounded-[28px] border border-slate-200 bg-white p-4 shadow-sm ${className}`}>
      {(title || subtitle) && (
        <div className="mb-4">
          {subtitle ? <p className="text-[12px] font-semibold uppercase tracking-[0.2em] text-slate-400">{subtitle}</p> : null}
          {title ? <h2 className="mt-1 text-[18px] font-semibold tracking-tight text-slate-900">{title}</h2> : null}
        </div>
      )}
      {children}
    </section>
  );
}
