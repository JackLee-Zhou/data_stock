import React, { useEffect, useState } from 'react';

/** 顶部 CTP 连接状态栏 */
export const CtpStatusBar: React.FC = () => {
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    const check = async () => {
      try {
        const r = await fetch('/api/v1/ctp/status');
        if (r.ok) {
          const d = await r.json();
          if (d.connected && d.loggedIn) {
            setStatus(`🟢 CTP ${d.tradingDay || ''} | ${d.subscribedCount} 合约`);
          } else if (d.connected) {
            setStatus(`🟡 CTP 已连接 未登录 ${d.lastError || ''}`);
          } else {
            setStatus(`🔴 CTP 未连接 ${d.lastError || ''}`);
          }
        }
      } catch { setStatus(null); }
    };
    check();
    const interval = setInterval(check, 10000);
    return () => clearInterval(interval);
  }, []);

  if (!status) return null;
  return (
    <div className="px-4 py-1.5 text-[11px] text-secondary-text bg-surface-hover border-b border-border">
      {status}
    </div>
  );
};
