import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { api } from "../api/client";

interface Props {
  documentId: string;
  highlightGuid: string | null;
}

interface SceneHandle {
  meshes: Map<string, THREE.Mesh>;
  render: () => void;
}

// Monochrome, per DESIGN.md: no accent colour. The cited element turns black.
const SOLID = new THREE.MeshStandardMaterial({ color: 0xe2e2e2, roughness: 0.9 });
const SPACE = new THREE.MeshStandardMaterial({
  color: 0xffffff,
  transparent: true,
  opacity: 0.12,
  depthWrite: false,
});
const HIGHLIGHT = new THREE.MeshStandardMaterial({ color: 0x000000, roughness: 0.6 });
const HIGHLIGHT_SPACE = new THREE.MeshStandardMaterial({
  color: 0x000000,
  transparent: true,
  opacity: 0.45,
  depthWrite: false,
});
const EDGES = new THREE.LineBasicMaterial({ color: 0x4b4b4b });

/** IFC model rendered from the backend's mesh JSON (one mesh per IFC GlobalId). */
export function ModelViewer({ documentId, highlightGuid }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const handle = useRef<SceneHandle | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "empty" | "error">("loading");

  useEffect(() => {
    const el = host.current;
    if (!el) return;
    let disposed = false;
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.setClearColor(0xffffff);
    el.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    scene.add(new THREE.HemisphereLight(0xffffff, 0xcccccc, 2.4));
    const sun = new THREE.DirectionalLight(0xffffff, 1.2);
    sun.position.set(30, 60, 20);
    scene.add(sun);
    const camera = new THREE.PerspectiveCamera(45, 1, 0.05, 10_000);
    const controls = new OrbitControls(camera, renderer.domElement);
    const render = () => renderer.render(scene, camera);
    controls.addEventListener("change", render);

    const resize = () => {
      const width = el.clientWidth;
      const height = Math.max(el.clientHeight, 1);
      renderer.setSize(width, height);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      render();
    };
    const observer = new ResizeObserver(resize);
    observer.observe(el);

    const meshes = new Map<string, THREE.Mesh>();
    api.mesh(documentId).then(
      (data) => {
        if (disposed) return;
        const group = new THREE.Group();
        for (const m of data.meshes) {
          const geometry = new THREE.BufferGeometry();
          geometry.setAttribute("position", new THREE.Float32BufferAttribute(m.positions, 3));
          geometry.setIndex(m.indices);
          geometry.computeVertexNormals();
          const isSpace = m.ifc_class === "IfcSpace";
          const mesh = new THREE.Mesh(geometry, isSpace ? SPACE : SOLID);
          mesh.userData = { isSpace };
          if (!isSpace)
            mesh.add(new THREE.LineSegments(new THREE.EdgesGeometry(geometry, 30), EDGES));
          group.add(mesh);
          meshes.set(m.guid, mesh);
        }
        scene.add(group);
        const box = new THREE.Box3().setFromObject(group);
        const center = box.getCenter(new THREE.Vector3());
        const radius = Math.max(box.getSize(new THREE.Vector3()).length(), 1);
        camera.position.copy(center).add(new THREE.Vector3(0.6, 0.7, 0.9).multiplyScalar(radius));
        controls.target.copy(center);
        controls.update();
        handle.current = { meshes, render };
        setStatus(data.meshes.length ? "ready" : "empty");
        render();
      },
      () => !disposed && setStatus("error"),
    );

    return () => {
      disposed = true;
      handle.current = null;
      observer.disconnect();
      controls.dispose();
      meshes.forEach((mesh) => {
        mesh.geometry.dispose();
        mesh.children.forEach((c) => (c as THREE.LineSegments).geometry.dispose());
      });
      renderer.dispose();
      el.removeChild(renderer.domElement);
    };
  }, [documentId]);

  useEffect(() => {
    const h = handle.current;
    if (!h) return;
    h.meshes.forEach((mesh, guid) => {
      const isSpace = Boolean(mesh.userData.isSpace);
      const lit = guid === highlightGuid;
      mesh.material = lit ? (isSpace ? HIGHLIGHT_SPACE : HIGHLIGHT) : isSpace ? SPACE : SOLID;
    });
    h.render();
  }, [highlightGuid, status]);

  return (
    <div className="model-viewer">
      <div ref={host} className="model-canvas" />
      {status !== "ready" && (
        <div className="viewer-empty overlay-message">
          {status === "loading" && "Loading 3D model…"}
          {status === "empty" && "The model has no geometry."}
          {status === "error" && "No 3D model yet. Drawings get one once their scale is known."}
        </div>
      )}
    </div>
  );
}
