// 太阳位置与日出日落（NOAA 简化算法）
// 用途：跟随模式（P1）下按嘉定经纬度 + 真实时间算太阳高度角/方位角，
// 驱动平行光方向、色温与强度，实现「与现实 1:1」的光照。

const D2R = Math.PI / 180;
const R2D = 180 / Math.PI;

// 一年中的第几天（1-366）
function dayOfYear(d) {
  const start = Date.UTC(d.getUTCFullYear(), 0, 1);
  return Math.floor((Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()) - start) / 864e5) + 1;
}

// 太阳赤纬与均时差（分钟）
function declAndEqTime(n) {
  const g = (2 * Math.PI / 365) * (n - 1);
  const eq =
    229.18 *
    (0.000075 + 0.001868 * Math.cos(g) - 0.032077 * Math.sin(g) -
      0.014615 * Math.cos(2 * g) - 0.040849 * Math.sin(2 * g));
  const dec =
    0.006918 - 0.399912 * Math.cos(g) + 0.070257 * Math.sin(g) -
    0.006758 * Math.cos(2 * g) + 0.000907 * Math.sin(2 * g) -
    0.002697 * Math.cos(3 * g) + 0.00148 * Math.sin(3 * g);
  return { eq, dec }; // dec 弧度，eq 分钟
}

/**
 * 太阳高度角与方位角
 * @param {Date} date 时间（用其 UTC 时刻；时区单独给）
 * @param {number} lat 纬度（北正）
 * @param {number} lon 经度（东正）
 * @param {number} tz  时区偏移（小时，如 +8）
 * @returns {{altitude:number, azimuth:number}} 角度制；方位角自正北顺时针 0-360
 */
export function solarPosition(date, lat, lon, tz) {
  const n = dayOfYear(date);
  const { eq, dec } = declAndEqTime(n);
  // 当地真太阳时（分钟）
  const utcMin = date.getUTCHours() * 60 + date.getUTCMinutes() + date.getUTCSeconds() / 60;
  const trueSolarMin = utcMin + eq + 4 * lon - 60 * 0; // UTC→当地：+4*lon 经度修正 + 均时差；时区只在显示用
  const ha = (trueSolarMin / 4 - 180) * D2R; // 时角（正午为 0，下午为正）
  const phi = lat * D2R;
  const sinAlt = Math.sin(phi) * Math.sin(dec) + Math.cos(phi) * Math.cos(dec) * Math.cos(ha);
  const altitude = Math.asin(Math.max(-1, Math.min(1, sinAlt))) * R2D;
  // 方位角
  const cosAz = (Math.sin(dec) - Math.sin(phi) * sinAlt) / (Math.cos(phi) * Math.cos(Math.asin(Math.max(-1, Math.min(1, sinAlt)))));
  let az = Math.acos(Math.max(-1, Math.min(1, cosAz))) * R2D;
  if (ha > 0) az = 360 - az; // 下午偏西
  return { altitude, azimuth: az };
}

/** 当天日出/日落，返回「当地分钟数」（0-1440） */
export function sunTimes(date, lat, lon, tz) {
  const n = dayOfYear(date);
  const { eq, dec } = declAndEqTime(n);
  const phi = lat * D2R;
  const cosHa = Math.cos(90.833 * D2R) / (Math.cos(phi) * Math.cos(dec)) - Math.tan(phi) * Math.tan(dec);
  if (cosHa > 1) return { rise: null, set: null, polar: 'night' };   // 极夜
  if (cosHa < -1) return { rise: null, set: null, polar: 'day' };    // 极昼
  const ha = Math.acos(cosHa) * R2D;
  // 720 - 4*(经度 + 时角) - 均时差 + 时区*60
  return { rise: 720 - 4 * (lon + ha) - eq + tz * 60, set: 720 - 4 * (lon - ha) - eq + tz * 60 };
}

/** 分钟数 → HH:MM */
export function hhmm(min) {
  if (min == null) return '--:--';
  const t = ((Math.round(min) % 1440) + 1440) % 1440;
  return `${String(Math.floor(t / 60)).padStart(2, '0')}:${String(t % 60).padStart(2, '0')}`;
}

/** WMO 天气代码 → 我们的四类 + 中文 */
export function weatherFromWmo(code, temp) {
  const c = Number(code);
  if (c >= 71 && c <= 77) return { weather: 'snow', text: '雪' };
  if (c === 85 || c === 86) return { weather: 'snow', text: '阵雪' };
  if ((c >= 51 && c <= 67) || (c >= 80 && c <= 82)) return { weather: 'rain', text: '雨' };
  if (c >= 95) return { weather: 'rain', text: '雷雨' };
  if (c === 45 || c === 48) return { weather: 'overcast', text: '雾' };
  if (c === 1 || c === 2) return { weather: 'overcast', text: '多云' };
  if (c === 3) return { weather: 'overcast', text: '阴' };
  // 0 晴；温度低于 1℃ 且仍在降水类已在上方处理
  if (temp != null && temp <= 1 && (c >= 70 || c >= 60)) return { weather: 'snow', text: '雪' };
  return { weather: 'sunny', text: '晴' };
}
