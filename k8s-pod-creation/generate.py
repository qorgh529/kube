#!/usr/bin/env python3
"""kubectl 로 Pod 6개(Deployment replicas=6)를 만들 때 클러스터 내부 흐름을
draw.io 다중 페이지(단계별) 다이어그램으로 생성한다.

실행: python3 generate.py  ->  pod-creation-flow.drawio
"""
import os
import xml.etree.ElementTree as ET

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pod-creation-flow.drawio")

POD_NAMES = ["x2k9p", "b7fqd", "m4zrl", "t8wcn", "q5hjs", "v3ndg"]
POD_IPS = ["10.244.1.11", "10.244.1.12", "10.244.2.21", "10.244.2.22", "10.244.3.31", "10.244.3.32"]
NODE_Y = [90, 310, 530]

# ---------------------------------------------------------------- 단계 정의
# active_nodes: 강조할 컴포넌트, active_edges: 애니메이션 화살표
# objects: etcd 에 저장된 오브젝트 상태, pods: 워커 노드 위 Pod 상태
STEPS = [
    dict(
        tab="0. 전체 흐름",
        title="전체 흐름 한눈에 보기 (①~⑨)",
        active_nodes=[], active_edges="ALL",
        objects="final", pods="running",
        desc=(
            "<b>명령:</b> <code>kubectl apply -f nginx-deploy.yaml</code> (replicas: 6) "
            "또는 <code>kubectl create deployment nginx --image=nginx --replicas=6</code><br><br>"
            "① kubectl → API Server 요청 &nbsp; ② 인증/인가/Admission &nbsp; ③ etcd 저장 후 응답 &nbsp; "
            "④ Deployment Controller → ReplicaSet 생성 &nbsp; ⑤ ReplicaSet Controller → Pod 6개 생성<br>"
            "⑥ Scheduler → 노드 배정(Binding) &nbsp; ⑦ kubelet 이 자기 노드의 Pod 감지 &nbsp; "
            "⑧ CRI(containerd)·CNI 로 컨테이너 실행 &nbsp; ⑨ 상태 보고 → Running 6/6<br><br>"
            "<b>핵심:</b> 모든 컴포넌트는 서로 직접 대화하지 않고 <b>오직 kube-apiserver 를 통해서만</b> 통신하며, "
            "각자 API Server 를 <b>watch</b> 하다가 '원하는 상태(desired)'와 '현재 상태(current)'의 차이를 메우는 "
            "<b>Reconciliation Loop</b> 로 동작합니다. 아래 탭(페이지)을 순서대로 넘겨 보세요."
        ),
    ),
    dict(
        tab="1. kubectl 요청",
        title="① kubectl 이 API Server 로 요청 전송",
        active_nodes=["client", "kubectl"], active_edges=["e_kubectl"],
        objects="none", pods="none",
        edge_labels={"e_kubectl": "① HTTPS POST<br>/apis/apps/v1/namespaces/default/deployments"},
        desc=(
            "• 사용자가 <code>kubectl apply -f nginx-deploy.yaml</code> 실행 (spec.replicas: 6)<br>"
            "• kubectl 은 <b>~/.kube/config</b> 에서 클러스터 주소·인증서·토큰·현재 context 를 읽음<br>"
            "• 클라이언트 측 검증 후 YAML 을 JSON 으로 변환하여 <b>kube-apiserver 의 REST API</b> 로 HTTPS 요청 전송<br>"
            "• 주의: kubectl 은 Pod 를 '직접' 만들지 않는다. <b>'Deployment 라는 원하는 상태'를 API Server 에 등록</b>할 뿐이다."
        ),
    ),
    dict(
        tab="2. API Server 처리",
        title="② kube-apiserver: 인증 → 인가 → Admission → 검증",
        active_nodes=["apiserver"], active_edges=["e_kubectl"],
        objects="none", pods="none",
        desc=(
            "• <b>Authentication(인증)</b>: 클라이언트 인증서 / Bearer Token / OIDC 등으로 '누구인가' 확인<br>"
            "• <b>Authorization(인가)</b>: RBAC 으로 'default 네임스페이스에 deployments 를 create 할 권한이 있는가' 확인<br>"
            "• <b>Mutating Admission</b>: 기본값 주입 등 요청 객체 수정 (예: DefaultStorageClass, 웹훅)<br>"
            "• <b>Schema Validation</b> → <b>Validating Admission</b>: ResourceQuota, LimitRange, PodSecurity 등 정책 검사<br>"
            "• 하나라도 실패하면 이 단계에서 4xx 에러가 kubectl 로 반환되고 아무 것도 저장되지 않는다."
        ),
    ),
    dict(
        tab="3. etcd 저장",
        title="③ etcd 에 Deployment 저장 → kubectl 에 201 Created 응답",
        active_nodes=["apiserver", "etcd", "objects"], active_edges=["e_etcd", "e_resp"],
        objects="deploy", pods="none",
        edge_labels={"e_etcd": "③ Deployment 저장", "e_resp": "③ 201 Created"},
        desc=(
            "• API Server 가 Deployment 오브젝트를 <b>etcd</b> (클러스터의 유일한 상태 저장소, key-value DB)에 기록<br>"
            "• kubectl 에 <b>201 Created</b> 응답 → 터미널에 <code>deployment.apps/nginx created</code> 출력<br>"
            "• <b>이 시점에 Pod 는 아직 0개!</b> kubectl 명령은 여기서 끝나고, 이후는 클러스터가 비동기로 처리한다.<br>"
            "• etcd 에 변화가 생기면 API Server 는 이를 watch 중인 컴포넌트들에게 이벤트(ADDED)를 전달한다."
        ),
    ),
    dict(
        tab="4. Deployment Ctrl",
        title="④ Deployment Controller: ReplicaSet 생성",
        active_nodes=["cm", "dc", "objects"], active_edges=["e_cm", "e_etcd"],
        objects="rs", pods="none",
        edge_labels={"e_cm": "④ watch Deployment<br>→ create ReplicaSet", "e_etcd": "④ ReplicaSet 저장"},
        desc=(
            "• kube-controller-manager 안의 <b>Deployment Controller</b> 가 Informer(watch)로 새 Deployment 이벤트 수신<br>"
            "• 이 Deployment 에 해당하는 ReplicaSet 이 없음을 확인 → <b>ReplicaSet</b> <code>nginx-7c5ddbdf54</code> "
            "(replicas: 6, pod-template-hash 라벨 포함) 생성을 API Server 에 요청<br>"
            "• API Server 는 ①~③ 과 같은 검증을 거쳐 ReplicaSet 을 etcd 에 저장 (ownerReference = Deployment)<br>"
            "• Deployment 는 롤링 업데이트/롤백을 위해 ReplicaSet 을 버전처럼 관리한다."
        ),
    ),
    dict(
        tab="5. ReplicaSet Ctrl",
        title="⑤ ReplicaSet Controller: Pod 6개 생성 (아직 노드 미배정)",
        active_nodes=["cm", "rsc", "objects"], active_edges=["e_cm", "e_etcd"],
        objects="pods_pending", pods="none",
        edge_labels={"e_cm": "⑤ watch ReplicaSet<br>→ create Pod × 6", "e_etcd": "⑤ Pod × 6 저장"},
        desc=(
            "• <b>ReplicaSet Controller</b> 가 새 ReplicaSet 감지: desired=6, current=0 → 차이 6개<br>"
            "• Pod 템플릿으로 <b>Pod 오브젝트 6개</b> 생성 요청 (slow-start 배치: 1 → 2 → 4 …개씩 생성)<br>"
            "• 각 Pod 은 etcd 에 저장되지만 <code>spec.nodeName</code> 이 <b>비어 있음</b> → 상태 <b>Pending</b><br>"
            "• 아직 어떤 노드에서도 컨테이너가 실행되지 않았다. 이것은 단지 'DB 상의 기록'일 뿐이다."
        ),
    ),
    dict(
        tab="6. Scheduler",
        title="⑥ kube-scheduler: 노드 선택 후 Binding",
        active_nodes=["sched", "objects"], active_edges=["e_sched", "e_etcd"],
        objects="pods_bound", pods="scheduled",
        edge_labels={"e_sched": "⑥ watch nodeName=''<br>→ Binding", "e_etcd": "⑥ nodeName 기록"},
        desc=(
            "• Scheduler 는 <code>spec.nodeName</code> 이 빈 Pod 을 watch → 스케줄링 큐에 6개 적재<br>"
            "• <b>Filtering</b>: CPU/메모리 requests 여유, nodeSelector, Affinity, Taint/Toleration, 포트 충돌 등으로 후보 노드 거르기<br>"
            "• <b>Scoring</b>: 리소스 균형, Pod 분산(topology spread), 이미지 존재 여부 등으로 점수 → 최고점 노드 선택<br>"
            "• <b>Binding</b>: API Server 에 Binding 요청 → Pod 의 nodeName 이 node-1/2/3 으로 기록 (예: 노드당 2개)<br>"
            "• Scheduler 는 '어디에 둘지'만 결정한다. 실제 실행은 하지 않는다."
        ),
    ),
    dict(
        tab="7. kubelet 감지",
        title="⑦ 각 노드의 kubelet 이 자신에게 배정된 Pod 감지",
        active_nodes=["kubelet0", "kubelet1", "kubelet2"], active_edges=["e_kl0", "e_kl1", "e_kl2"],
        objects="pods_bound", pods="scheduled",
        edge_labels={k: "⑦ watch Pod<br>(nodeName=자기 노드)" for k in ["e_kl0", "e_kl1", "e_kl2"]},
        desc=(
            "• 모든 워커 노드의 <b>kubelet</b> 은 <code>spec.nodeName == 자기 노드</code> 인 Pod 을 API Server 에서 watch<br>"
            "• node-1, node-2, node-3 의 kubelet 이 각각 2개씩 새 Pod 을 발견<br>"
            "• kubelet 은 노드 수준 admission(리소스 확인 등)을 한 번 더 수행한 뒤 Pod 실행 준비를 시작한다<br>"
            "• kubelet 은 노드의 '현장 감독' 역할 — API 에 기록된 PodSpec 을 실제 컨테이너로 만든다."
        ),
    ),
    dict(
        tab="8. 컨테이너 실행",
        title="⑧ kubelet → CRI(containerd) / CNI / CSI 로 컨테이너 실행",
        active_nodes=["rt0", "rt1", "rt2"],
        active_edges=["e_cri0", "e_cri1", "e_cri2", "e_pa0", "e_pb0", "e_pa1", "e_pb1", "e_pa2", "e_pb2"],
        objects="pods_creating", pods="creating",
        edge_labels={**{f"e_cri{i}": "⑧ CRI (gRPC)" for i in range(3)}},
        desc=(
            "• kubelet → <b>CRI</b>(gRPC) 로 container runtime(containerd/CRI-O)에 <code>RunPodSandbox</code> 호출 → "
            "<b>pause 컨테이너</b>가 네트워크 네임스페이스를 잡음<br>"
            "• <b>CNI 플러그인</b>(Calico, Flannel, Cilium 등)이 Pod IP 할당 및 네트워크 연결 (예: 10.244.x.x)<br>"
            "• 볼륨이 있다면 <b>CSI</b> 로 마운트 → 이미지 <b>Pull</b>(nginx) → <code>CreateContainer</code> / <code>StartContainer</code><br>"
            "• 이 동안 <code>kubectl get pods</code> 에는 STATUS <b>ContainerCreating</b> 으로 보인다."
        ),
    ),
    dict(
        tab="9. 상태 보고",
        title="⑨ kubelet 이 상태 보고 → Running 6/6 완료",
        active_nodes=["kubelet0", "kubelet1", "kubelet2", "apiserver", "etcd", "objects", "kubectl"],
        active_edges=["e_kl0", "e_kl1", "e_kl2", "e_etcd", "e_resp"],
        objects="final", pods="running",
        edge_labels={**{f"e_kl{i}": "⑨ PATCH pod status<br>(Running / Ready)" for i in range(3)},
                     "e_etcd": "⑨ status 저장", "e_resp": "⑨ kubectl get pods"},
        desc=(
            "• kubelet 이 컨테이너 상태와 <b>Readiness/Liveness Probe</b> 결과를 API Server 에 보고 → etcd 에 "
            "<code>status.phase=Running</code>, <code>Ready=True</code>, podIP 기록<br>"
            "• ReplicaSet Controller 가 readyReplicas=6 확인, Deployment 상태도 <b>6/6 AVAILABLE</b> 로 갱신<br>"
            "• (Service 가 있다면 EndpointSlice 컨트롤러가 Pod IP 를 등록하고 kube-proxy 가 iptables/IPVS 규칙 갱신)<br>"
            "• <code>kubectl get pods</code> → <b>6개 Pod 모두 Running</b>. 이후 Pod 하나가 죽으면 ⑤부터 다시 반복(자가 치유)."
        ),
    ),
]

# 전체 화면(0번 탭)의 화살표 라벨
OVERVIEW_LABELS = {
    "e_kubectl": "① ② POST Deployment<br>(인증·인가·Admission)",
    "e_resp": "③ 201 Created",
    "e_etcd": "③④⑤⑥⑨ 읽기/쓰기",
    "e_cm": "④ ReplicaSet 생성<br>⑤ Pod × 6 생성",
    "e_sched": "⑥ Binding<br>(nodeName 지정)",
    **{f"e_kl{i}": "⑦ watch / ⑨ status" for i in range(3)},
    **{f"e_cri{i}": "⑧ CRI" for i in range(3)},
}

# ---------------------------------------------------------------- 스타일
C_ACTIVE = "#E8590C"
C_EDGE_ACTIVE = "#E03131"
C_EDGE_IDLE = "#C4C4C4"
C_EDGE_OVERVIEW = "#495057"


def box_style(fill, stroke, active=False, extra=""):
    s = (f"rounded=1;whiteSpace=wrap;html=1;arcSize=8;fillColor={fill};strokeColor={stroke};"
         f"fontSize=13;verticalAlign=middle;")
    if active:
        s += f"strokeColor={C_ACTIVE};strokeWidth=4;shadow=1;"
    return s + extra


class Page:
    def __init__(self, step_idx, step):
        self.i = step_idx
        self.s = step
        self.root = ET.Element("root")
        ET.SubElement(self.root, "mxCell", id="0")
        ET.SubElement(self.root, "mxCell", id="1", parent="0")
        self.overview = step["active_edges"] == "ALL"

    def active(self, cid):
        return cid in self.s["active_nodes"]

    def vertex(self, cid, value, style, x, y, w, h):
        c = ET.SubElement(self.root, "mxCell", id=cid, value=value, style=style, vertex="1", parent="1")
        ET.SubElement(c, "mxGeometry", x=str(x), y=str(y), width=str(w), height=str(h), **{"as": "geometry"})
        return c

    def edge(self, cid, src, tgt, style, points=None, both=False):
        if self.overview:
            on, label = True, OVERVIEW_LABELS.get(cid, "")
            color, width, anim = C_EDGE_OVERVIEW, 2, 0
        else:
            on = cid in self.s["active_edges"]
            label = self.s.get("edge_labels", {}).get(cid, "") if on else ""
            color, width, anim = (C_EDGE_ACTIVE, 3, 1) if on else (C_EDGE_IDLE, 1.5, 0)
        st = (f"edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;endArrow=block;endFill=1;"
              f"strokeColor={color};strokeWidth={width};flowAnimation={anim};fontSize=11;"
              f"fontColor={C_EDGE_ACTIVE if (on and not self.overview) else '#343A40'};fontStyle=1;"
              f"labelBackgroundColor=#FFFFFF;{style}")
        if both:
            st += "startArrow=block;startFill=1;"
        if not on:
            st += "dashed=1;"
        c = ET.SubElement(self.root, "mxCell", id=cid, value=label, style=st, edge="1",
                          parent="1", source=src, target=tgt)
        g = ET.SubElement(c, "mxGeometry", relative="1", **{"as": "geometry"})
        if points:
            arr = ET.SubElement(g, "Array", **{"as": "points"})
            for px, py in points:
                ET.SubElement(arr, "mxPoint", x=str(px), y=str(py))

    # ------------------------------------------------------------ 그리기
    def build(self):
        s = self.s
        # 제목 + 진행 표시줄
        self.vertex("title", f"<b>kubectl 로 Pod 6개 생성 시 클러스터 내부 동작</b> &nbsp;—&nbsp; {s['title']}",
                    "text;html=1;fontSize=20;align=left;verticalAlign=middle;", 30, 5, 1540, 36)
        for k, st in enumerate(STEPS):
            cur = k == self.i
            done = k < self.i and self.i != 0
            fill = C_ACTIVE if cur else ("#FFE8CC" if done else "#F1F3F5")
            font = "#FFFFFF" if cur else "#495057"
            self.vertex(f"chip{k}", st["tab"],
                        f"rounded=1;html=1;arcSize=40;fillColor={fill};strokeColor=none;fontColor={font};"
                        f"fontSize=12;fontStyle={1 if cur else 0};",
                        30 + k * 154, 46, 148, 28)

        # 클라이언트
        self.vertex("client", "", box_style("#F8F9FA", "#868E96", self.active("client"),
                                            "verticalAlign=top;dashed=1;"), 30, 100, 220, 360)
        self.vertex("client_lbl", "<b>👤 Client (사용자 PC)</b>", "text;html=1;fontSize=14;align=center;",
                    30, 105, 220, 26)
        yaml = ("<div style='text-align:left;font-family:monospace;font-size:11px'>"
                "# nginx-deploy.yaml<br>apiVersion: apps/v1<br>kind: Deployment<br>metadata:<br>"
                "&nbsp;&nbsp;name: nginx<br>spec:<br>&nbsp;&nbsp;<b style='color:#E03131'>replicas: 6</b><br>"
                "&nbsp;&nbsp;template:<br>&nbsp;&nbsp;&nbsp;&nbsp;spec:<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;containers:<br>"
                "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- image: nginx</div>")
        self.vertex("yaml", yaml, "rounded=1;html=1;whiteSpace=wrap;fillColor=#FFFFFF;strokeColor=#CED4DA;"
                    "align=left;spacingLeft=6;fontSize=11;", 45, 135, 190, 180)
        self.vertex("kubectl", "<b>kubectl</b><br><span style='font-size:11px'>apply -f nginx-deploy.yaml</span>",
                    box_style("#E7F5FF", "#1C7ED6", self.active("kubectl")), 45, 330, 190, 60)
        self.vertex("kubeconfig", "~/.kube/config<br>(서버 주소·인증서)",
                    "rounded=1;html=1;whiteSpace=wrap;fillColor=#FFF9DB;strokeColor=#FAB005;fontSize=10;",
                    65, 400, 150, 40)

        # 컨트롤 플레인
        self.vertex("cp", "", "rounded=1;html=1;arcSize=3;fillColor=#EDF2FF;strokeColor=#4263EB;"
                    "strokeWidth=2;", 290, 90, 650, 650)
        self.vertex("cp_lbl", "<b>☸ Control Plane (Master Node)</b>",
                    "text;html=1;fontSize=15;fontColor=#364FC7;align=left;", 305, 95, 400, 28)

        self.vertex("cm", "", box_style("#F3F0FF", "#7048E8", self.active("cm"), "verticalAlign=top;"),
                    310, 135, 290, 165)
        self.vertex("cm_lbl", "<b>kube-controller-manager</b>", "text;html=1;fontSize=13;align=center;",
                    310, 140, 290, 24)
        self.vertex("dc", "Deployment Controller<br><span style='font-size:10px'>Deployment → ReplicaSet</span>",
                    box_style("#FFFFFF", "#9775FA", self.active("dc"), "fontSize=12;"), 325, 172, 260, 50)
        self.vertex("rsc", "ReplicaSet Controller<br><span style='font-size:10px'>ReplicaSet → Pod × N</span>",
                    box_style("#FFFFFF", "#9775FA", self.active("rsc"), "fontSize=12;"), 325, 235, 260, 50)

        self.vertex("sched", "<b>kube-scheduler</b><br><br><span style='font-size:11px'>"
                    "Filtering → Scoring → Binding<br>(어느 노드에 둘지 결정)</span>",
                    box_style("#FFF0F6", "#D6336C", self.active("sched")), 640, 135, 280, 165)

        self.vertex("apiserver", "<b style='font-size:16px'>kube-apiserver</b><br><span style='font-size:11px'>"
                    "AuthN → AuthZ(RBAC) → Admission → Validation<br>모든 통신의 유일한 관문 (REST + watch)</span>",
                    box_style("#DBE4FF", "#3B5BDB", self.active("apiserver"), "strokeWidth=2;"),
                    450, 370, 330, 110)

        self.vertex("etcd", "<b>etcd</b><br><span style='font-size:11px'>클러스터 상태 저장소</span>",
                    "shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;size=12;fillColor=#E6FCF5;"
                    f"strokeColor={C_ACTIVE if self.active('etcd') else '#0CA678'};"
                    f"strokeWidth={4 if self.active('etcd') else 2};fontSize=14;",
                    700, 580, 170, 120)

        self.vertex("objects", self.objects_html(),
                    box_style("#FFFFFF", "#0CA678", self.active("objects"),
                              "align=left;verticalAlign=top;spacingLeft=8;spacingTop=4;fontSize=11;dashed=1;"),
                    310, 530, 360, 190)

        # 워커 노드
        for n, y in enumerate(NODE_Y):
            self.vertex(f"node{n}", "", "rounded=1;html=1;arcSize=4;fillColor=#F4FCE3;strokeColor=#5C940D;"
                        "strokeWidth=2;", 990, y, 580, 200)
            self.vertex(f"node{n}_lbl", f"<b>🖥 Worker Node-{n + 1}</b>",
                        "text;html=1;fontSize=13;fontColor=#2B8A3E;align=left;", 1000, y + 4, 200, 24)
            self.vertex(f"kubelet{n}", "<b>kubelet</b><br><span style='font-size:10px'>노드 에이전트</span>",
                        box_style("#FFF4E6", "#F76707", self.active(f"kubelet{n}")), 1010, y + 40, 150, 55)
            self.vertex(f"rt{n}", "<b>Container Runtime</b><br><span style='font-size:10px'>containerd + CNI</span>",
                        box_style("#E3FAFC", "#1098AD", self.active(f"rt{n}")), 1010, y + 125, 150, 55)
            self.vertex(f"kp{n}", "kube-proxy", "rounded=1;html=1;fillColor=#F8F9FA;strokeColor=#ADB5BD;"
                        "fontSize=10;fontColor=#868E96;", 1200, y + 6, 80, 22)
            for p in range(2):
                self.pod(n, p, 1230 + p * 170, y + 35)

        # 화살표
        self.edge("e_kubectl", "kubectl", "apiserver",
                  "exitX=1;exitY=0.3;exitDx=0;exitDy=0;entryX=0;entryY=0.3;entryDx=0;entryDy=0;",
                  points=[(390, 348), (390, 403)])
        self.edge("e_resp", "apiserver", "kubectl",
                  "exitX=0;exitY=0.8;exitDx=0;exitDy=0;entryX=1;entryY=0.8;entryDx=0;entryDy=0;",
                  points=[(330, 458), (330, 378)])
        self.edge("e_etcd", "apiserver", "etcd",
                  "exitX=0.85;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0;", both=True)
        self.edge("e_cm", "cm", "apiserver",
                  "exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0.2;entryY=0;entryDx=0;entryDy=0;", both=True)
        self.edge("e_sched", "sched", "apiserver",
                  "exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0.8;entryY=0;entryDx=0;entryDy=0;", both=True)
        for n, y in enumerate(NODE_Y):
            ky = y + 67
            self.edge(f"e_kl{n}", "apiserver", f"kubelet{n}",
                      "exitX=1;exitY=0.5;exitDx=0;exitDy=0;entryX=0;entryY=0.5;entryDx=0;entryDy=0;",
                      points=[(960, 425), (960, ky)], both=True)
            self.edge(f"e_cri{n}", f"kubelet{n}", f"rt{n}",
                      "exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0;")
            self.edge(f"e_pa{n}", f"rt{n}", f"pod{n}_0",
                      "exitX=1;exitY=0.5;exitDx=0;exitDy=0;entryX=0;entryY=0.82;entryDx=0;entryDy=0;")
            self.edge(f"e_pb{n}", f"rt{n}", f"pod{n}_1",
                      "exitX=0.85;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=1;entryDx=0;entryDy=0;",
                      points=[(1137, y + 192), (1475, y + 192)])

        # 설명 패널
        self.vertex("desc", f"<b style='font-size:15px;color:{C_ACTIVE}'>{s['title']}</b><br><br>{s['desc']}",
                    "rounded=1;html=1;whiteSpace=wrap;arcSize=4;fillColor=#FFFFFF;strokeColor=#ADB5BD;"
                    "align=left;verticalAlign=top;spacing=14;fontSize=13;", 30, 760, 1540, 200)
        if self.i != 0:
            nxt = "다음 단계 ▶ 아래 탭에서 다음 페이지" if self.i < len(STEPS) - 1 else "끝 ✔ 6/6 Running"
            self.vertex("hint", nxt, "text;html=1;fontSize=11;fontColor=#868E96;align=right;",
                        1270, 962, 300, 20)
        return self.root

    def pod(self, n, p, x, y):
        state = self.s["pods"]
        idx = n * 2 + p
        name = f"nginx-7c5ddbdf54-{POD_NAMES[idx]}"
        cid = f"pod{n}_{p}"
        base = "rounded=1;html=1;whiteSpace=wrap;arcSize=10;fontSize=11;verticalAlign=middle;"
        if state == "none":
            self.vertex(cid, "<span style='color:#ADB5BD'>(빈 자리)</span>",
                        base + "fillColor=none;strokeColor=#DEE2E6;dashed=1;", x, y, 160, 120)
        elif state == "scheduled":
            self.vertex(cid, f"<b>Pod</b><br><span style='font-size:9px'>{name}</span><br><br>"
                        "<b style='color:#E67700'>Pending</b><br><span style='font-size:10px'>nodeName 배정됨<br>"
                        "컨테이너 없음</span>",
                        base + "fillColor=#FFF9DB;strokeColor=#F08C00;dashed=1;strokeWidth=2;", x, y, 160, 120)
        elif state == "creating":
            self.vertex(cid, f"<b>Pod</b><br><span style='font-size:9px'>{name}</span><br>"
                        f"<b style='color:#D9480F'>ContainerCreating</b><br><span style='font-size:10px'>"
                        f"pause + nginx 기동 중<br>IP {POD_IPS[idx]}</span>",
                        base + "fillColor=#FFE8CC;strokeColor=#E8590C;strokeWidth=2;", x, y, 160, 120)
        else:
            self.vertex(cid, f"<b>Pod</b><br><span style='font-size:9px'>{name}</span><br>"
                        f"<b style='color:#2B8A3E'>● Running 1/1</b><br><span style='font-size:10px'>"
                        f"🐳 nginx 컨테이너<br>IP {POD_IPS[idx]}</span>",
                        base + "fillColor=#D3F9D8;strokeColor=#2B8A3E;strokeWidth=2;", x, y, 160, 120)

    def objects_html(self):
        o = self.s["objects"]
        head = "<b style='font-size:12px'>📦 etcd 에 저장된 오브젝트</b><br>"
        if o == "none":
            return head + "<br><span style='color:#ADB5BD'>(아직 아무것도 저장되지 않음)</span>"
        lines = ["✔ Deployment <b>nginx</b> (replicas: 6)"]
        if o == "deploy":
            lines.append("<span style='color:#ADB5BD'>ReplicaSet 없음 · Pod 0개</span>")
        if o != "deploy":
            cur = {"rs": 0}.get(o, 6)
            lines.append(f"✔ ReplicaSet <b>nginx-7c5ddbdf54</b> (desired 6 / current {cur})")
        if o == "rs":
            lines.append("<span style='color:#ADB5BD'>Pod 0개</span>")
        pod_line = {
            "pods_pending": "✔ Pod × 6 — <b style='color:#E67700'>Pending</b>, nodeName: <i>(없음)</i>",
            "pods_bound": "✔ Pod × 6 — <b style='color:#E67700'>Pending</b>, nodeName: node-1/2/3",
            "pods_creating": "✔ Pod × 6 — <b style='color:#D9480F'>ContainerCreating</b>",
            "final": "✔ Pod × 6 — <b style='color:#2B8A3E'>Running, Ready 6/6</b>",
        }.get(o)
        if pod_line:
            lines.append(pod_line)
        if o == "final":
            lines.append("✔ Deployment status: <b>6/6 AVAILABLE</b>")
        return head + "<br>".join(lines)


def main():
    mxfile = ET.Element("mxfile", host="app.diagrams.net", type="device")
    for i, step in enumerate(STEPS):
        d = ET.SubElement(mxfile, "diagram", id=f"step-{i}", name=step["tab"])
        model = ET.SubElement(d, "mxGraphModel", dx="1600", dy="1050", grid="0", gridSize="10",
                              guides="1", tooltips="1", connect="1", arrows="1", fold="1", page="1",
                              pageScale="1", pageWidth="1600", pageHeight="1000", math="0", shadow="0",
                              background="#FFFFFF")
        model.append(Page(i, step).build())
    ET.indent(mxfile)
    ET.ElementTree(mxfile).write(OUT, encoding="utf-8", xml_declaration=False)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
