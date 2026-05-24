"use client";

import type { ReactNode } from "react";

type DataTableProps = {
  headers: ReactNode[];
  rows: ReactNode[][];
  emptyMessage?: string;
  className?: string;
};

export function DataTable({ headers, rows, emptyMessage = "No records yet.", className = "" }: DataTableProps) {
  return (
    <div className={`overflow-hidden rounded-3xl border border-white/10 bg-white/5 shadow-glow ${className}`}>
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-white/10">
          <thead className="bg-white/5">
            <tr>
              {headers.map((header, index) => (
                <th
                  key={index}
                  className="px-4 py-3 text-left text-[0.72rem] font-semibold uppercase tracking-[0.24em] text-slate-300"
                >
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-white/8">
            {rows.length === 0 ? (
              <tr>
                <td className="px-4 py-8 text-sm text-slate-400" colSpan={headers.length}>
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              rows.map((row, rowIndex) => (
                <tr key={rowIndex} className="transition-colors hover:bg-white/[0.03]">
                  {row.map((cell, cellIndex) => (
                    <td key={cellIndex} className="px-4 py-4 align-top text-sm text-slate-200">
                      {cell}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

