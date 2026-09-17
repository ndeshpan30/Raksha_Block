'use client';

import React, { useEffect, useRef, useState } from 'react';
import { BundledBlock } from '@/types/raksha';

interface CorridorMapViewProps {
  blocks: BundledBlock[];
  selectedBlock: BundledBlock | null;
  onSelectBlock: (block: BundledBlock) => void;
  filterSection?: string;
}

interface StationInfo {
  code: string;
  name: string;
  km: number;
  lat: number;
  lng: number;
}

// Geographical topology of the 8 track sections along Delhi-Kanpur-DDU mainline
const STATIONS: StationInfo[] = [
  { code: 'NDLS', name: 'New Delhi', km: 0.0, lat: 28.6429, lng: 77.2195 },
  { code: 'TKJ', name: 'Tilak Bridge', km: 3.5, lat: 28.6256, lng: 77.2411 },
  { code: 'GZB', name: 'Ghaziabad Jn', km: 24.5, lat: 28.6534, lng: 77.4328 },
  { code: 'ALJN', name: 'Aligarh Jn', km: 126.0, lat: 27.8974, lng: 78.0880 },
  { code: 'TDL', name: 'Tundla Jn', km: 204.0, lat: 27.2065, lng: 78.2384 },
  { code: 'CNB', name: 'Kanpur Central', km: 435.0, lat: 26.4539, lng: 80.3514 },
  { code: 'PRYJ', name: 'Prayagraj Jn', km: 630.0, lat: 25.4484, lng: 81.8340 },
  { code: 'DDU', name: 'Pt. Deen Dayal Upadhyaya', km: 783.0, lat: 25.2815, lng: 83.1189 },
  { code: 'MB', name: 'Moradabad Jn', km: 165.0, lat: 28.8288, lng: 78.7768 },
];

// Mapping section code to start/end stations for coordinate interpolation
const SECTION_ENDPOINTS: Record<string, { from: string; to: string }> = {
  'SEC-NDLS-TKJ': { from: 'NDLS', to: 'TKJ' },
  'SEC-TKJ-GZB': { from: 'TKJ', to: 'GZB' },
  'SEC-GZB-ALJN': { from: 'GZB', to: 'ALJN' },
  'SEC-ALJN-TDL': { from: 'ALJN', to: 'TDL' },
  'SEC-TDL-CNB': { from: 'TDL', to: 'CNB' },
  'SEC-CNB-PRYJ': { from: 'CNB', to: 'PRYJ' },
  'SEC-PRYJ-DDU': { from: 'PRYJ', to: 'DDU' },
  'SEC-GZB-MB': { from: 'GZB', to: 'MB' },
};

export const CorridorMapView: React.FC<CorridorMapViewProps> = ({
  blocks,
  selectedBlock,
  onSelectBlock,
  filterSection = 'ALL',
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const [leafletReady, setLeafletReady] = useState<boolean>(false);
  const mapInstanceRef = useRef<any>(null);
  const markersGroupRef = useRef<any>(null);

  // Filter blocks by active section filter
  const displayedBlocks = filterSection === 'ALL'
    ? blocks
    : blocks.filter((b) => b.section_id === filterSection);

  // Load Leaflet dynamically via CDN script injection to avoid Next.js SSR window errors
  useEffect(() => {
    if (typeof window === 'undefined') return;

    if ((window as any).L) {
      setLeafletReady(true);
      return;
    }

    // Add Leaflet CSS
    if (!document.getElementById('leaflet-css')) {
      const link = document.createElement('link');
      link.id = 'leaflet-css';
      link.rel = 'stylesheet';
      link.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
      document.head.appendChild(link);
    }

    // Add Leaflet JS
    if (!document.getElementById('leaflet-js')) {
      const script = document.createElement('script');
      script.id = 'leaflet-js';
      script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
      script.async = true;
      script.onload = () => {
        setLeafletReady(true);
      };
      document.head.appendChild(script);
    }
  }, []);

  // Initialize and update Leaflet Map
  useEffect(() => {
    if (!leafletReady || !mapContainerRef.current || typeof window === 'undefined') return;
    const L = (window as any).L;
    if (!L) return;

    // Initialize map if not yet initialized
    if (!mapInstanceRef.current) {
      const map = L.map(mapContainerRef.current, {
        center: [27.2, 79.5],
        zoom: 7,
        zoomControl: true,
      });

      // CartoDB Dark Matter tile layer for high-contrast railway HUD
      L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
        subdomains: 'abcd',
        maxZoom: 18,
      }).addTo(map);

      // Draw Indian Railways Corridor Track Line
      const trackPoints = [
        [28.6429, 77.2195], // NDLS
        [28.6256, 77.2411], // TKJ
        [28.6534, 77.4328], // GZB
        [27.8974, 78.0880], // ALJN
        [27.2065, 78.2384], // TDL
        [26.4539, 80.3514], // CNB
        [25.4484, 81.8340], // PRYJ
        [25.2815, 83.1189], // DDU
      ];

      L.polyline(trackPoints, {
        color: '#38bdf8',
        weight: 4,
        opacity: 0.8,
        dashArray: '8, 8',
      }).addTo(map);

      // GZB to MB branch track
      L.polyline([[28.6534, 77.4328], [28.8288, 78.7768]], {
        color: '#818cf8',
        weight: 3,
        opacity: 0.7,
        dashArray: '6, 6',
      }).addTo(map);

      // Add Station Icons & Markers
      STATIONS.forEach((stn) => {
        const stationIcon = L.divIcon({
          className: 'custom-station-pin',
          html: `<div style="
            background: #0f172a;
            border: 2px solid #38bdf8;
            color: #38bdf8;
            border-radius: 6px;
            padding: 2px 5px;
            font-size: 10px;
            font-weight: 800;
            font-family: monospace;
            white-space: nowrap;
            box-shadow: 0 0 10px rgba(56, 189, 248, 0.4);
          ">${stn.code}</div>`,
          iconSize: [40, 20],
          iconAnchor: [20, 10],
        });

        L.marker([stn.lat, stn.lng], { icon: stationIcon })
          .addTo(map)
          .bindPopup(`<b>${stn.name} (${stn.code})</b><br>Mainline Chainage: KM ${stn.km}`);
      });

      markersGroupRef.current = L.layerGroup().addTo(map);
      mapInstanceRef.current = map;
    }

    // Clear and redraw block markers
    if (markersGroupRef.current) {
      markersGroupRef.current.clearLayers();

      displayedBlocks.forEach((block) => {
        const endpoints = SECTION_ENDPOINTS[block.section_id];
        if (!endpoints) return;

        const stnFrom = STATIONS.find((s) => s.code === endpoints.from);
        const stnTo = STATIONS.find((s) => s.code === endpoints.to);
        if (!stnFrom || !stnTo) return;

        // Linear interpolation along section chainage
        const spanKm = Math.max(1, stnTo.km - stnFrom.km);
        const midKm = (block.start_km + block.end_km) / 2;
        const ratio = Math.max(0, Math.min(1, (midKm - stnFrom.km) / spanKm));

        const lat = stnFrom.lat + ratio * (stnTo.lat - stnFrom.lat);
        const lng = stnFrom.lng + ratio * (stnTo.lng - stnFrom.lng);

        const isBundled = block.bundled_request_ids.length > 1;
        const isSelected = selectedBlock?.block_id === block.block_id;

        const pinColor = isBundled
          ? (block.departments_involved.length >= 3 ? '#ef4444' : '#06b6d4')
          : (block.departments_involved.includes('TRD') ? '#eab308' : block.departments_involved.includes('S&T') ? '#a855f7' : '#f97316');

        const blockPin = L.divIcon({
          className: 'custom-block-marker',
          html: `<div style="
            width: ${isSelected ? '22px' : '16px'};
            height: ${isSelected ? '22px' : '16px'};
            background: ${pinColor};
            border: 2px solid ${isSelected ? '#ffffff' : '#0f172a'};
            border-radius: 50%;
            cursor: pointer;
            box-shadow: 0 0 ${isSelected ? '14px' : '8px'} ${pinColor};
            transition: all 0.2s ease;
          "></div>`,
          iconSize: [22, 22],
          iconAnchor: [11, 11],
        });

        const marker = L.marker([lat, lng], { icon: blockPin })
          .addTo(markersGroupRef.current)
          .on('click', () => {
            onSelectBlock(block);
          });

        marker.bindPopup(`
          <div style="font-family: sans-serif; font-size: 11px; color: #0f172a; line-height: 1.4;">
            <b style="color: #0284c7;">${block.block_id}</b> [${block.approval_status}]<br/>
            <b>Section:</b> ${block.section_id} (KM ${block.start_km.toFixed(1)}-${block.end_km.toFixed(1)})<br/>
            <b>Window:</b> ${block.scheduled_start.slice(11, 16)} - ${block.scheduled_end.slice(11, 16)} (${block.total_duration_minutes}m)<br/>
            <b>Depts:</b> ${block.departments_involved.join(', ')}<br/>
            <b>Savings:</b> <span style="color: #16a34a; font-weight: bold;">+${block.savings_minutes} mins</span>
          </div>
        `);
      });
    }
  }, [leafletReady, displayedBlocks, selectedBlock, onSelectBlock]);

  return (
    <div className="bg-slate-900 border border-slate-700/80 rounded-2xl overflow-hidden shadow-2xl flex flex-col">
      {/* Map Header Toolbar */}
      <div className="p-4 bg-slate-950 border-b border-slate-800 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 rounded-lg bg-blue-500/20 border border-blue-500/40 flex items-center justify-center text-blue-400 font-bold text-sm">
            🗺️
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h3 className="text-sm font-bold text-white tracking-wide">
                Delhi–Howrah Golden Corridor 2D GIS Network Map
              </h3>
              <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 border border-blue-500/30">
                Leaflet GIS
              </span>
            </div>
            <p className="text-[11px] text-slate-400 mt-0.5">
              Plotting {displayedBlocks.length} scheduled maintenance blocks across 8 mainline track sections
            </p>
          </div>
        </div>

        {/* Legend */}
        <div className="flex items-center space-x-3 text-[11px] text-slate-300 bg-slate-900/90 px-3 py-1.5 rounded-xl border border-slate-800">
          <div className="flex items-center space-x-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-red-500 shadow-sm" />
            <span>Triple Bundle (3 Depts)</span>
          </div>
          <div className="flex items-center space-x-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 shadow-sm" />
            <span>Dual Bundle (2 Depts)</span>
          </div>
          <div className="flex items-center space-x-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-orange-500 shadow-sm" />
            <span>ENG</span>
          </div>
          <div className="flex items-center space-x-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-purple-500 shadow-sm" />
            <span>S&amp;T</span>
          </div>
          <div className="flex items-center space-x-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-yellow-400 shadow-sm" />
            <span>TRD</span>
          </div>
        </div>
      </div>

      {/* Map Container */}
      <div className="relative w-full h-[480px] bg-slate-950">
        <div ref={mapContainerRef} className="w-full h-full" />

        {/* Selected Block HUD Overlay */}
        {selectedBlock && (
          <div className="absolute bottom-4 left-4 z-[400] bg-slate-900/95 backdrop-blur-md border border-slate-700/80 rounded-xl p-3 shadow-2xl text-xs max-w-sm">
            <div className="flex items-center justify-between space-x-2">
              <span className="font-mono font-bold text-white text-sm">{selectedBlock.block_id}</span>
              <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 border border-blue-500/30">
                {selectedBlock.approval_status}
              </span>
            </div>
            <div className="text-[11px] text-slate-300 mt-1.5 space-y-0.5">
              <div><strong className="text-slate-400">Section:</strong> {selectedBlock.section_id} (KM {selectedBlock.start_km.toFixed(1)} - {selectedBlock.end_km.toFixed(1)})</div>
              <div><strong className="text-slate-400">Window:</strong> {selectedBlock.scheduled_start.slice(11, 16)} - {selectedBlock.scheduled_end.slice(11, 16)} ({selectedBlock.total_duration_minutes}m)</div>
              <div><strong className="text-slate-400">Departments:</strong> {selectedBlock.departments_involved.join(', ')}</div>
              <div><strong className="text-emerald-400">Savings:</strong> +{selectedBlock.savings_minutes} mins line possession</div>
            </div>
            <div className="mt-2 pt-2 border-t border-slate-800 text-[10px] text-slate-400">
              * Click "Why this block?" in side drawer for complete AI constraint proof
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
