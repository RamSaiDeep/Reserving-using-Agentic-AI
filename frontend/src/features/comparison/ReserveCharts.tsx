'use client';
import React from 'react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
  AreaChart,
  Area,
  LineChart,
  Line,
} from 'recharts';
import { fmtShort, CurrencyCode } from '@/lib/utils';
import { MethodResultItem } from '@/types';

interface ReserveChartsProps {
  barChartData: { name: string; IBNR: number; Ultimate: number }[];
  trendData: { ay: number; paid: number; ibnr: number; ultimate: number; pctReported: number; settlementRate: number }[];
  selectedMethodName: string;
  currency: CurrencyCode;
}

export default function ReserveCharts({
  barChartData,
  trendData,
  selectedMethodName,
  currency,
}: ReserveChartsProps) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 text-left">
      {/* 1. Bar Chart: Comparative Ultimate Claims */}
      <div className="bg-bg-1 border border-border rounded-xl p-5 shadow-sm">
        <h4 className="text-xs font-bold text-text-sub uppercase tracking-wider mb-4">
          Ultimate Claims Comparison by Reserving Model
        </h4>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={barChartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2a2a2a" />
              <XAxis dataKey="name" stroke="#888" fontSize={9} tickLine={false} />
              <YAxis stroke="#888" fontSize={9} tickLine={false} tickFormatter={(v) => fmtShort(v)} />
              <Tooltip
                contentStyle={{ backgroundColor: '#181818', borderColor: '#2d2d2d' }}
                labelStyle={{ fontWeight: 'bold', color: '#fff', fontSize: 11 }}
                itemStyle={{ fontSize: 11 }}
                formatter={(value: any) => [fmtShort(value), '']}
              />
              <Legend wrapperStyle={{ fontSize: 10, paddingTop: 10 }} />
              <Bar dataKey="IBNR" fill="#10b981" radius={[2, 2, 0, 0]} />
              <Bar dataKey="Ultimate" fill="#5b7cfc" radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* 2. Area Chart: Claims Composition by Accident Year */}
      <div className="bg-bg-1 border border-border rounded-xl p-5 shadow-sm">
        <h4 className="text-xs font-bold text-text-sub uppercase tracking-wider mb-4">
          Reserving Composition: {selectedMethodName}
        </h4>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={trendData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2a2a2a" />
              <XAxis dataKey="ay" stroke="#888" fontSize={9} tickLine={false} />
              <YAxis stroke="#888" fontSize={9} tickLine={false} tickFormatter={(v) => fmtShort(v)} />
              <Tooltip
                contentStyle={{ backgroundColor: '#181818', borderColor: '#2d2d2d' }}
                labelStyle={{ fontWeight: 'bold', color: '#fff', fontSize: 11 }}
                itemStyle={{ fontSize: 11 }}
                formatter={(value: any) => [fmtShort(value), '']}
              />
              <Legend wrapperStyle={{ fontSize: 10, paddingTop: 10 }} />
              <Area type="monotone" dataKey="paid" stackId="1" stroke="#5b7cfc" fill="#5b7cfc" fillOpacity={0.6} />
              <Area type="monotone" dataKey="ibnr" stackId="1" stroke="#10b981" fill="#10b981" fillOpacity={0.6} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
