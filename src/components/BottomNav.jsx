import { NAV_ITEMS } from "../app/navigation";

export function BottomNav({ active, onChange }) {
  return (
    <div className="border-t border-slate-200 bg-white/95 px-2 py-3 backdrop-blur">
      <div className="grid grid-cols-5 items-end gap-1">
        {NAV_ITEMS.map((tab) => {
          const isActive = active === tab.id;
          const isPrimary = tab.id === "ai";
          return (
            <button
              key={tab.id}
              onClick={() => onChange(tab.id)}
              className={`flex flex-col items-center justify-center rounded-2xl px-2 py-2 text-[11px] font-medium ${
                isActive ? "bg-blue-50 text-blue-700" : "text-slate-400"
              } ${isPrimary ? "-mt-7" : ""}`}
            >
              <span
                className={`grid leading-none ${
                  isPrimary
                    ? "mb-1 h-14 w-14 place-items-center rounded-[24px] bg-blue-600 text-[22px] text-white shadow-lg shadow-blue-100"
                    : "text-[18px]"
                }`}
              >
                {tab.icon}
              </span>
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
