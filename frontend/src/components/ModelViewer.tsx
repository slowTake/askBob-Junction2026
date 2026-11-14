import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { api } from "../api/client";
import { isTranslucent, materialRole, type MaterialRole } from "../lib/materials";
import { WebGLUnavailable } from "../lib/webgl";

interface Props {
  documentId: string;
  highlightGuid: string | null;
  omitted?: number; // meshes left out of a very large model (they are still in the data)
}

interface SceneHandle {
  meshes: Map<string, THREE.Mesh>;
  render: () => void;
}

// Neutral model; the cited element takes the accent blue (DESIGN.md, D-012).
// The canvas is transparent so the theme's desk colour shows behind it.
const LOOKS: Record<MaterialRole, THREE.Material> = {
  solid: new THREE.MeshStandardMaterial({ color: 0xe2e2e2, roughness: 0.9 }),
  fixture: new THREE.MeshStandardMaterial({ color: 0xafafaf, roughness: 0.8 }),
  marker: new THREE.MeshStandardMaterial({ color: 0x4b4b4b, roughness: 0.8 }),
  space: new THREE.MeshStandardMaterial({
    color: 0xffffff,
    transparent: true,
    opacity: 0.12,
    depthWrite: false,
  }),
  glass: new THREE.MeshStandardMaterial({
    color: 0xffffff,
    transparent: true,
    opacity: 0.35,
    depthWrite: false,
  }),
};
const HIGHLIGHT = new THREE.MeshStandardMaterial({ color: 0x0f62fe, roughness: 0.6 });
const HIGHLIGHT_SEE_THROUGH = new THREE.MeshStandardMaterial({
  color: 0x0f62fe,
  transparent: true,
  opacity: 0.45,
  depthWrite: false,
});
const EDGES = new THREE.LineBasicMaterial({ color: 0x6f6f6f });

/** IFC model rendered from the backend's mesh JSON (one mesh per IFC GlobalId). */
export function ModelViewer({ documentId, highlightGuid, omitted = 0 }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const handle = useRef<SceneHandle | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "empty" | "error">("loading");

  useEffect(() => {
    const el = host.current;
    if (!el) return;
    let disposed = false;
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    } catch {
      throw new WebGLUnavailable(); // the ErrorBoundary around the viewer explains it
    }
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.setClearColor(0x000000, 0);
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
          const role = materialRole(m.ifc_class);
          const mesh = new THREE.Mesh(geometry, LOOKS[role]);
          mesh.userData = { role };
          if (!isTranslucent(role))
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
      const role = mesh.userData.role as MaterialRole;
      const lit = guid === highlightGuid;
      mesh.material = lit ? (isTranslucent(role) ? HIGHLIGHT_SEE_THROUGH : HIGHLIGHT) : LOOKS[role];
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
      {status === "ready" && omitted > 0 && (
        <p className="model-note">
          Large model: {omitted.toLocaleString()} small parts are not drawn in 3D. They are still
          counted in answers.
        </p>
      )}
    </div>
  );
}
