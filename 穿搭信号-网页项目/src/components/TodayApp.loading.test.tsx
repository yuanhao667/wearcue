import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
const mocks = vi.hoisted(() => ({ api: vi.fn(), weather: vi.fn(), locate: vi.fn(), loginLocation: vi.fn(), cached: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("./TrackingBear", () => ({ TrackingBear: () => <div data-testid="bear" /> }));
vi.mock("./OutfitIcon", () => ({ OutfitIcon: () => null }));
vi.mock("@/lib/backend-api", () => ({ apiJson: mocks.api }));
vi.mock("@/lib/browser-weather", () => ({ fetchBrowserWeather: mocks.weather }));
vi.mock("@/lib/browser-location", () => ({ locateCurrentDistrict: mocks.locate, takeLoginLocation: mocks.loginLocation, simplifyLocationName: (value: string) => value || "" }));
vi.mock("@/lib/today-session", () => ({ readTodaySession: mocks.cached, saveTodaySession: vi.fn(), clearTodaySession: vi.fn() }));
import { TodayApp } from "./TodayApp";

const settings = { city_id: "geo-39.9-116.4", city_name: "朝阳区", latitude: 39.9, longitude: 116.4, timezone: "Asia/Shanghai", audience: "mens", cold_offset: 0 };
const weather = { city: "朝阳区", latitude: 39.9, longitude: 116.4, timezone: "Asia/Shanghai", date: "2026-10-28", apparent_min: 0, apparent_max: 12, current_apparent_temperature: 10, weather_code: 3, max_precipitation_probability: 0, max_wind_gust: 24, uv_index_max: 4 };
const recommendation = { template_id: "test", label: "浅灰工装日常", source: "system", scene: "commute", audience: "mens", constraints: { apparent_delta: 12, thermal_band: "cold" }, items: [] };
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>((done) => { resolve = done; }); return { promise, resolve }; }

beforeEach(() => { vi.clearAllMocks(); localStorage.clear(); mocks.cached.mockReturnValue(null); mocks.loginLocation.mockReturnValue(null); });
afterEach(cleanup);

it("shows both card shells immediately and weather without waiting for the recommendation or GPS", async () => {
  const forecast = deferred<typeof weather>();
  const outfit = deferred<typeof recommendation>();
  mocks.api.mockImplementation((path: string) => path === "/settings" ? Promise.resolve(settings) : path === "/recommendations/preview" ? outfit.promise : Promise.resolve({ swap: { remaining: 6, limit: 6 } }));
  mocks.weather.mockReturnValue(forecast.promise);
  const { container } = render(<TodayApp />);
  expect(container.querySelector(".weather-paper-card")).toBeInTheDocument();
  expect(container.querySelector(".recommendation-copy-card")).toBeInTheDocument();
  await waitFor(() => expect(mocks.weather).toHaveBeenCalledWith(39.9, 116.4, "朝阳区"));
  expect(mocks.locate).not.toHaveBeenCalled();
  await act(async () => forecast.resolve(weather));
  expect(screen.getByText("多云")).toBeInTheDocument();
  expect(screen.getByText("天气已就绪，正在匹配穿搭")).toBeInTheDocument();
  await act(async () => outfit.resolve(recommendation));
  expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("试试这套浅灰工装日常");
  expect(screen.getByRole("button", { name: "查看穿搭方案" })).toBeInTheDocument();
});

it("keeps the weather card usable when the recommendation fails and allows retry", async () => {
  mocks.api.mockImplementation((path: string) => path === "/settings" ? Promise.resolve(settings) : path === "/recommendations/preview" ? Promise.reject(new Error("推荐暂时不可用")) : Promise.resolve({ swap: {} }));
  mocks.weather.mockResolvedValue(weather);
  render(<TodayApp />);
  await screen.findByText("推荐暂时不可用");
  expect(screen.getByText("多云")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "重新加载" }));
  await waitFor(() => expect(mocks.weather).toHaveBeenCalledTimes(2));
});

it("restores a valid session without repeating settings, location, weather or recommendation calls", async () => {
  mocks.cached.mockReturnValue({ settings, weather, recommendation, seenTemplateIdsByScene: {} });
  mocks.api.mockResolvedValue({ swap: {} });
  render(<TodayApp />);
  await screen.findByRole("button", { name: "查看穿搭方案" });
  expect(mocks.weather).not.toHaveBeenCalled();
  expect(mocks.locate).not.toHaveBeenCalled();
  expect(mocks.api.mock.calls.every(([path]) => path === "/ai-usage-quota")).toBe(true);
});
