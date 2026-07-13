import React from 'react';
import { LineChart, Line, ResponsiveContainer, YAxis } from 'recharts';
import { TrendingUp, TrendingDown } from 'lucide-react';

export const TrendBadge = ({ value, isPositive, label }) => {
  const Icon = isPositive ? TrendingUp : TrendingDown;
  return (
    <span className={`trend-badge ${isPositive ? 'trend-up' : 'trend-down'}`} title={label}>
      <Icon size={12} />
      {Math.abs(value).toFixed(1)}%
    </span>
  );
};

export const KPICard = ({ title, value, subtext, icon: Icon, color, sparklineData, sparklineDataKey, trend }) => {
  return (
    <div className="panel kpi-card" style={{ borderLeft: `4px solid ${color}` }}>
      <div className="kpi-header">
        <span className="kpi-label">{title}</span>
        {Icon && <Icon size={20} color={color} />}
      </div>
      
      <div className="kpi-body">
        <span className="kpi-value">{value}</span>
        {trend && <TrendBadge {...trend} />}
      </div>

      {sparklineData && sparklineData.length > 0 && (
        <div className="kpi-sparkline">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={sparklineData}>
              <YAxis domain={['dataMin', 'dataMax']} hide />
              <Line type="monotone" dataKey={sparklineDataKey} stroke={color} strokeWidth={2} dot={false} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {subtext && <span className="kpi-subtext">{subtext}</span>}
    </div>
  );
};
