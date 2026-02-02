import React, { useState, useMemo } from "react";
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Cell,
} from "recharts";
import styles from "./DataChart.module.css";

export interface ChartVisualization {
  type: "bar" | "line" | "pie" | "area";
  title?: string;
  xKey: string;
  yKeys?: string[];
  nameKey?: string;
  valueKey?: string;
  data: Record<string, unknown>[];
}

interface DataChartProps {
  visualization: ChartVisualization;
}

const CHART_COLORS = [
  "#0078D4", // Microsoft Blue
  "#107C10", // Green
  "#FFB900", // Yellow
  "#D83B01", // Orange
  "#8764B8", // Purple
  "#00B7C3", // Teal
  "#E74856", // Red
  "#567C73", // Sage
];

const MAX_BAR_ITEMS = 10;
const MAX_PIE_ITEMS = 8;

type ChartType = "bar" | "line" | "pie" | "area";

const CHART_TYPE_OPTIONS: { value: ChartType; label: string; icon: string }[] = [
  { value: "bar", label: "Bar", icon: "📊" },
  { value: "line", label: "Line", icon: "📈" },
  { value: "pie", label: "Pie", icon: "🥧" },
  { value: "area", label: "Area", icon: "📉" },
];

export const DataChart: React.FC<DataChartProps> = ({ visualization }) => {
  const [showChart, setShowChart] = useState(true);
  const [selectedChartType, setSelectedChartType] = useState<ChartType>(visualization.type);
  const { title, data } = visualization;

  // Limit data for certain chart types
  const chartData = useMemo(() => {
    if (selectedChartType === "bar" && data.length > MAX_BAR_ITEMS) {
      return data.slice(0, MAX_BAR_ITEMS);
    }
    if (selectedChartType === "pie" && data.length > MAX_PIE_ITEMS) {
      return data.slice(0, MAX_PIE_ITEMS);
    }
    return data;
  }, [data, selectedChartType]);

  const isDataTruncated =
    (selectedChartType === "bar" && data.length > MAX_BAR_ITEMS) ||
    (selectedChartType === "pie" && data.length > MAX_PIE_ITEMS);

  const truncatedCount = selectedChartType === "pie" ? MAX_PIE_ITEMS : MAX_BAR_ITEMS;

  if (!data || data.length === 0) {
    return null;
  }

  const renderBarChart = () => {
    const { xKey, yKeys = [] } = visualization;

    // Truncate long labels for display
    const truncateLabel = (label: string, maxLength = 20) => {
      if (typeof label !== 'string') return String(label);
      return label.length > maxLength ? label.substring(0, maxLength) + '...' : label;
    };

    return (
      <ResponsiveContainer width="100%" height={Math.max(300, chartData.length * 35)}>
        <BarChart
          data={chartData}
          layout="vertical"
          margin={{ top: 20, right: 30, left: 120, bottom: 20 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" horizontal={true} vertical={false} />
          <XAxis type="number" tick={{ fontSize: 12 }} />
          <YAxis
            type="category"
            dataKey={xKey}
            tick={{ fontSize: 11 }}
            width={110}
            tickFormatter={(value) => truncateLabel(value, 18)}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "#fff",
              border: "1px solid #ccc",
              borderRadius: "4px",
            }}
            formatter={(value) => (typeof value === 'number' ? value.toLocaleString() : value)}
          />
          <Legend wrapperStyle={{ paddingTop: 10 }} />
          {yKeys.map((key, index) => (
            <Bar
              key={key}
              dataKey={key}
              fill={CHART_COLORS[index % CHART_COLORS.length]}
              name={key.replace(/_/g, " ")}
              radius={[0, 4, 4, 0]}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    );
  };

  const renderLineChart = () => {
    const { xKey, yKeys = [] } = visualization;
    return (
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 60 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
          <XAxis
            dataKey={xKey}
            tick={{ fontSize: 12 }}
            angle={-45}
            textAnchor="end"
            interval={0}
            height={80}
          />
          <YAxis tick={{ fontSize: 12 }} />
          <Tooltip
            contentStyle={{
              backgroundColor: "#fff",
              border: "1px solid #ccc",
              borderRadius: "4px",
            }}
          />
          <Legend wrapperStyle={{ paddingTop: 10 }} />
          {yKeys.map((key, index) => (
            <Line
              key={key}
              type="monotone"
              dataKey={key}
              stroke={CHART_COLORS[index % CHART_COLORS.length]}
              strokeWidth={2}
              dot={{ r: 4 }}
              name={key.replace(/_/g, " ")}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    );
  };

  const renderPieChart = () => {
    const { xKey, yKeys = [] } = visualization;
    // For pie charts, use xKey as nameKey and first yKey as valueKey
    const nameKey = visualization.nameKey || xKey;
    const valueKey = visualization.valueKey || yKeys[0];
    if (!nameKey || !valueKey) return null;

    return (
      <ResponsiveContainer width="100%" height={350}>
        <PieChart>
          <Pie
            data={chartData}
            dataKey={valueKey}
            nameKey={nameKey}
            cx="50%"
            cy="50%"
            outerRadius={100}
            label={({ name, percent }) => {
              const truncatedName = typeof name === 'string' && name.length > 15
                ? name.substring(0, 15) + '...'
                : name;
              return `${truncatedName}: ${((percent ?? 0) * 100).toFixed(1)}%`;
            }}
            labelLine={{ stroke: "#666", strokeWidth: 1 }}
          >
            {chartData.map((_, index) => (
              <Cell
                key={`cell-${index}`}
                fill={CHART_COLORS[index % CHART_COLORS.length]}
              />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              backgroundColor: "#fff",
              border: "1px solid #ccc",
              borderRadius: "4px",
            }}
            formatter={(value) => (typeof value === 'number' ? value.toLocaleString() : value)}
          />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    );
  };

  const renderAreaChart = () => {
    const { xKey, yKeys = [] } = visualization;
    return (
      <ResponsiveContainer width="100%" height={300}>
        <AreaChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 60 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
          <XAxis
            dataKey={xKey}
            tick={{ fontSize: 12 }}
            angle={-45}
            textAnchor="end"
            interval={0}
            height={80}
          />
          <YAxis tick={{ fontSize: 12 }} />
          <Tooltip
            contentStyle={{
              backgroundColor: "#fff",
              border: "1px solid #ccc",
              borderRadius: "4px",
            }}
          />
          <Legend wrapperStyle={{ paddingTop: 10 }} />
          {yKeys.map((key, index) => (
            <Area
              key={key}
              type="monotone"
              dataKey={key}
              stroke={CHART_COLORS[index % CHART_COLORS.length]}
              fill={CHART_COLORS[index % CHART_COLORS.length]}
              fillOpacity={0.3}
              name={key.replace(/_/g, " ")}
            />
          ))}
        </AreaChart>
      </ResponsiveContainer>
    );
  };

  const renderChart = () => {
    switch (selectedChartType) {
      case "bar":
        return renderBarChart();
      case "line":
        return renderLineChart();
      case "pie":
        return renderPieChart();
      case "area":
        return renderAreaChart();
      default:
        return null;
    }
  };

  return (
    <div className={styles.chartContainer}>
      <div className={styles.chartHeader}>
        {title && <h4 className={styles.chartTitle}>{title}</h4>}
        <div className={styles.chartControls}>
          <div className={styles.chartTypeSelector}>
            {CHART_TYPE_OPTIONS.map((option) => (
              <button
                key={option.value}
                className={`${styles.chartTypeButton} ${selectedChartType === option.value ? styles.chartTypeButtonActive : ''}`}
                onClick={() => setSelectedChartType(option.value)}
                title={option.label}
              >
                {option.icon}
              </button>
            ))}
          </div>
          <button
            className={styles.toggleButton}
            onClick={() => setShowChart(!showChart)}
            aria-label={showChart ? "Hide chart" : "Show chart"}
          >
            {showChart ? "Hide" : "Show"}
          </button>
        </div>
      </div>
      {showChart && (
        <div className={styles.chartWrapper}>
          {renderChart()}
          {isDataTruncated && (
            <p className={styles.truncationNote}>
              Showing top {truncatedCount} of {data.length} items. See table below for full data.
            </p>
          )}
        </div>
      )}
    </div>
  );
};

export default DataChart;
