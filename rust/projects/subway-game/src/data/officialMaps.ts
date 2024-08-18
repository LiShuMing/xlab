import { CityData, Route, Station } from '../types';
import beijingMapSrc from '../assets/maps/beijing-rail-transit-2026.gif';
import hangzhouMapSrc from '../assets/maps/hangzhou-metro.png';
import shanghaiMapSrc from '../assets/maps/shanghai-metro.gif';
import wuhanMapSrc from '../assets/maps/wuhan-metro.gif';

export interface MapPoint {
  x: number;
  y: number;
}

interface OfficialMapConfig {
  src: string;
  width: number;
  height: number;
  title: string;
  stationPoints?: Record<string, MapPoint>;
}

const beijingStationPoints: Record<string, MapPoint> = {
  古城: { x: 358, y: 1094 },
  五棵松: { x: 654, y: 1080 },
  公主坟: { x: 728, y: 1075 },
  军事博物馆: { x: 790, y: 1040 },
  复兴门: { x: 840, y: 965 },
  西单: { x: 940, y: 990 },
  天安门东: { x: 1046, y: 988 },
  王府井: { x: 1120, y: 990 },
  东单: { x: 1170, y: 940 },
  建国门: { x: 1242, y: 930 },
  国贸: { x: 1368, y: 935 },
  四惠: { x: 1512, y: 942 },
  西直门: { x: 740, y: 804 },
  车公庄: { x: 802, y: 872 },
  宣武门: { x: 928, y: 1080 },
  前门: { x: 1056, y: 1054 },
  崇文门: { x: 1156, y: 1046 },
  北京站: { x: 1238, y: 1004 },
  朝阳门: { x: 1240, y: 842 },
  东直门: { x: 1214, y: 742 },
  雍和宫: { x: 1118, y: 688 },
  鼓楼大街: { x: 972, y: 704 },
  积水潭: { x: 856, y: 728 },
  圆明园: { x: 666, y: 652 },
  海淀黄庄: { x: 724, y: 828 },
  平安里: { x: 846, y: 844 },
  菜市口: { x: 924, y: 1145 },
  北京南站: { x: 944, y: 1302 },
  天通苑: { x: 1112, y: 526 },
  惠新西街南口: { x: 1116, y: 754 },
  东四: { x: 1168, y: 880 },
  天坛东门: { x: 1146, y: 1160 },
  宋家庄: { x: 1168, y: 1416 },
  海淀五路居: { x: 544, y: 896 },
  慈寿寺: { x: 632, y: 956 },
  南锣鼓巷: { x: 1046, y: 782 },
  金台路: { x: 1350, y: 812 },
  青年路: { x: 1544, y: 918 },
  北京西站: { x: 768, y: 1198 },
  达官营: { x: 842, y: 1196 },
  珠市口: { x: 1048, y: 1124 },
  磁器口: { x: 1148, y: 1106 },
  广渠门外: { x: 1254, y: 1094 },
  双井: { x: 1370, y: 1068 },
  九龙山: { x: 1460, y: 1098 },
  奥林匹克公园: { x: 1012, y: 560 },
  巴沟: { x: 654, y: 820 },
  知春路: { x: 790, y: 744 },
  牡丹园: { x: 900, y: 736 },
  芍药居: { x: 1224, y: 640 },
  三元桥: { x: 1360, y: 742 },
  呼家楼: { x: 1342, y: 884 },
  十里河: { x: 1396, y: 1226 },
  角门西: { x: 970, y: 1374 },
  六里桥: { x: 742, y: 1218 },
  蒲黄榆: { x: 1160, y: 1222 },
  将台: { x: 1502, y: 660 }
};

export const officialMaps: Record<string, OfficialMapConfig> = {
  beijing: {
    src: beijingMapSrc,
    width: 2000,
    height: 2000,
    title: '北京城市轨道交通线网图',
    stationPoints: beijingStationPoints
  },
  hangzhou: {
    src: hangzhouMapSrc,
    width: 1772,
    height: 1403,
    title: '杭州地铁运营线网图'
  },
  wuhan: {
    src: wuhanMapSrc,
    width: 2732,
    height: 2731,
    title: '武汉轨道交通线网图'
  },
  shanghai: {
    src: shanghaiMapSrc,
    width: 2279,
    height: 3189,
    title: '上海轨道交通网络示意图'
  }
};

function getFallbackPoint(station: Station, cityData: CityData, config: OfficialMapConfig): MapPoint {
  const stations = cityData.lines.flatMap(line => line.stations);
  const maxX = Math.max(...stations.map(item => item.x));
  const maxY = Math.max(...stations.map(item => item.y));
  if (maxX <= config.width && maxY <= config.height) {
    return { x: station.x, y: station.y };
  }

  const minX = Math.min(...stations.map(item => item.x));
  const minY = Math.min(...stations.map(item => item.y));
  const normX = (station.x - minX) / (maxX - minX || 1);
  const normY = (station.y - minY) / (maxY - minY || 1);

  return {
    x: config.width * 0.18 + normX * config.width * 0.64,
    y: config.height * 0.24 + (1 - normY) * config.height * 0.56
  };
}

export function getOfficialMapConfig(cityId: string): OfficialMapConfig | null {
  return officialMaps[cityId] || null;
}

export function getOfficialMapPoint(
  station: Station,
  cityData: CityData,
  config: OfficialMapConfig
): MapPoint {
  return config.stationPoints?.[station.name] || getFallbackPoint(station, cityData, config);
}

export function getQuestionFocusPoints(
  cityData: CityData,
  startStation: Station,
  endStation: Station,
  highlightRoute: Route | null,
  config: OfficialMapConfig
): MapPoint[] {
  const stations = highlightRoute?.stations.length
    ? highlightRoute.stations
    : [startStation, endStation];

  return stations.map(station => getOfficialMapPoint(station, cityData, config));
}
