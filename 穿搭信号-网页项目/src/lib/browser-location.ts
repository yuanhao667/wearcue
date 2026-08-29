import type { City } from "@/domain/types";

type ReverseLocation = {
  locality?: string;
  city?: string;
  principalSubdivision?: string;
  countryName?: string;
  localityInfo?: { administrative?: Array<{ name?: string }> };
};

const traditionalLocationCharacters: Record<string, string> = {
  區: "区", 縣: "县", 陽: "阳", 陰: "阴", 臺: "台", 灣: "湾", 門: "门", 頭: "头",
  豐: "丰", 順: "顺", 義: "义", 興: "兴", 懷: "怀", 雲: "云", 慶: "庆", 寧: "宁",
  遼: "辽", 龍: "龙", 廣: "广", 東: "东", 濱: "滨", 澤: "泽", 莊: "庄", 嶺: "岭",
  島: "岛", 烏: "乌", 蘭: "兰", 漢: "汉", 張: "张", 馬: "马", 鳳: "凤", 長: "长",
  樂: "乐", 鄉: "乡", 鎮: "镇",
};

export function simplifyLocationName(name?: string) {
  return (name ?? "").replace(/[區縣陽陰臺灣門頭豐順義興懷雲慶寧遼龍廣東濱澤莊嶺島烏蘭漢張馬鳳長樂鄉鎮]/g, (character) => traditionalLocationCharacters[character] ?? character);
}

export function districtName(location: ReverseLocation) {
  const districts = (location.localityInfo?.administrative ?? [])
    .map((item) => simplifyLocationName(item.name?.trim()))
    .filter((name) => name !== "市辖区" && /[区县]$/.test(name));
  return districts.at(-1) || simplifyLocationName(location.locality || location.city) || "当前位置";
}

function currentCoordinates() {
  return new Promise<GeolocationCoordinates>((resolve, reject) => {
    if (!navigator.geolocation) return reject(new Error("当前浏览器不支持定位"));
    navigator.geolocation.getCurrentPosition(
      (position) => resolve(position.coords),
      (error) => reject(new Error(error.code === 1 ? "请允许浏览器获取位置" : error.code === 3 ? "定位超时，请重试" : "暂时无法获取位置")),
      { enableHighAccuracy: true, timeout: 10_000, maximumAge: 300_000 },
    );
  });
}

export async function locateCurrentDistrict(): Promise<City> {
  const { latitude, longitude } = await currentCoordinates();
  const url = new URL("https://api.bigdatacloud.net/data/reverse-geocode-client");
  url.searchParams.set("latitude", String(latitude));
  url.searchParams.set("longitude", String(longitude));
  url.searchParams.set("localityLanguage", "zh-CN");
  const response = await fetch(url);
  if (!response.ok) throw new Error("位置名称获取失败，请重试");
  const location = await response.json() as ReverseLocation;
  return {
    id: `geo-${latitude.toFixed(4)}-${longitude.toFixed(4)}`,
    name: districtName(location),
    admin1: simplifyLocationName(location.principalSubdivision),
    country: simplifyLocationName(location.countryName) || "中国",
    latitude,
    longitude,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "Asia/Shanghai",
  };
}
