
import { useEffect, useRef } from "react";
import * as THREE from "three";
import { brainModules } from "../data/brainModules";

interface BrainProps {
  onSelectModule: (moduleId: string | null) => void;
  selectedModuleId: string | null;
}

function Brain({ onSelectModule, selectedModuleId }: BrainProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const onSelectModuleRef = useRef(onSelectModule);
  const selectedModuleIdRef = useRef(selectedModuleId);

  useEffect(() => {
    onSelectModuleRef.current = onSelectModule;
  }, [onSelectModule]);

  useEffect(() => {
    selectedModuleIdRef.current = selectedModuleId;
  }, [selectedModuleId]);

  useEffect(() => {
    const container = containerRef.current;

    if (!container) {
      return;
    }

    const scene = new THREE.Scene();

    const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
    camera.position.set(0, 0, 8);

    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
    });

    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(container.clientWidth, container.clientHeight);
    container.appendChild(renderer.domElement);

    const brainGroup = new THREE.Group();
    scene.add(brainGroup);

    const geometries: THREE.BufferGeometry[] = [];
    const materials: THREE.Material[] = [];
    const moduleNodes = new Map<string, THREE.Mesh>();

    const coreGeometry = new THREE.SphereGeometry(0.55, 32, 32);
    const coreMaterial = new THREE.MeshStandardMaterial({
      color: 0x4c9eff,
      emissive: 0x173f70,
      roughness: 0.3,
      metalness: 0.6,
      wireframe: true,
    });

    geometries.push(coreGeometry);
    materials.push(coreMaterial);

    const core = new THREE.Mesh(coreGeometry, coreMaterial);
    brainGroup.add(core);

    const moduleGeometry = new THREE.SphereGeometry(0.22, 24, 24);
    geometries.push(moduleGeometry);

    for (const module of brainModules) {
      const moduleMaterial = new THREE.MeshStandardMaterial({
        color: module.color,
        emissive: module.color,
        emissiveIntensity: 0.25,
        roughness: 0.35,
        metalness: 0.5,
      });

      materials.push(moduleMaterial);

      const node = new THREE.Mesh(moduleGeometry, moduleMaterial);
      node.position.set(...module.position);
      node.userData.moduleId = module.id;

      moduleNodes.set(module.id, node);
      brainGroup.add(node);

      const points = [
        new THREE.Vector3(0, 0, 0),
        new THREE.Vector3(...module.position),
      ];

      const connectionGeometry = new THREE.BufferGeometry().setFromPoints(points);
      const connectionMaterial = new THREE.LineBasicMaterial({
        color: module.color,
        transparent: true,
        opacity: 0.45,
      });

      geometries.push(connectionGeometry);
      materials.push(connectionMaterial);

      brainGroup.add(
        new THREE.Line(connectionGeometry, connectionMaterial)
      );
    }

    scene.add(new THREE.AmbientLight(0xffffff, 1.5));

    const mainLight = new THREE.PointLight(0x5ba9ff, 35);
    mainLight.position.set(3, 3, 5);
    scene.add(mainLight);

    const secondaryLight = new THREE.PointLight(0x7e57c2, 15);
    secondaryLight.position.set(-3, -2, -3);
    scene.add(secondaryLight);

    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();

    const handlePointerDown = (event: PointerEvent) => {
      const rect = renderer.domElement.getBoundingClientRect();

      pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

      raycaster.setFromCamera(pointer, camera);

      const nodes = Array.from(moduleNodes.values());
      const intersections = raycaster.intersectObjects(nodes);

      if (intersections.length > 0) {
        const moduleId = intersections[0].object.userData.moduleId as string;
        onSelectModuleRef.current(moduleId);
      } else {
        onSelectModuleRef.current(null);
      }
    };

    renderer.domElement.addEventListener("pointerdown", handlePointerDown);

    const resizeObserver = new ResizeObserver(() => {
      const width = container.clientWidth;
      const height = container.clientHeight;

      if (width === 0 || height === 0) {
        return;
      }

      camera.aspect = width / height;
      camera.position.z = camera.aspect < 0.8 ? 11 : 8;
      camera.updateProjectionMatrix();

      renderer.setSize(width, height);
    });

    resizeObserver.observe(container);

    let animationFrame = 0;

    const animate = () => {
      animationFrame = requestAnimationFrame(animate);

      brainGroup.rotation.y += 0.0015;
      brainGroup.rotation.x += 0.0005;

      for (const [moduleId, node] of moduleNodes) {
        const material = node.material as THREE.MeshStandardMaterial;
        const selected = moduleId === selectedModuleIdRef.current;

        material.emissiveIntensity = selected ? 1.2 : 0.25;
        node.scale.setScalar(selected ? 1.35 : 1);
      }

      renderer.render(scene, camera);
    };

    animate();

    return () => {
      cancelAnimationFrame(animationFrame);
      resizeObserver.disconnect();

      renderer.domElement.removeEventListener(
        "pointerdown",
        handlePointerDown
      );

      for (const geometry of geometries) {
        geometry.dispose();
      }

      for (const material of materials) {
        material.dispose();
      }

      renderer.dispose();
      renderer.domElement.remove();
    };
  }, []);

  return <div ref={containerRef} className="brain-container" />;
}

export default Brain;
