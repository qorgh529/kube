# kubectl 로 Pod 6개를 만들 때 클러스터 안에서 일어나는 일

`pod-creation-flow.drawio` 는 **12개 페이지(탭)** 로 된 draw.io 다이어그램입니다.
`전체 흐름` 탭에서 전체 그림을 보고, `0` ~ `10` 탭을 차례로 넘기면 단계별 진행 상황을 볼 수 있습니다.
클러스터는 **Google Cloud(GCE VM 3대, asia-northeast3 a/b/c)** 위에 있다고 가정하고, 
클라우드와 대화하는 **cloud-controller-manager(CCM)** 와 **Cloud Provider API(GCP)** 도 함께 그렸습니다.
각 단계에서 동작 중인 컴포넌트는 **주황색 테두리**로, 데이터가 오가는 화살표는 **빨간색 애니메이션**으로 표시됩니다.

## HTML 버전 (추천)

`pod-creation-flow.html` 을 브라우저로 열면 바로 볼 수 있습니다 (인터넷 연결 불필요, 파일 하나로 동작).

- 위쪽 단계 버튼을 누르거나 **◀ 이전 / 다음 ▶**, 키보드 **← →** 로 이동
- **▶ 자동 재생**(또는 Space)을 누르면 ⓪~⑩ 단계가 4.5초 간격으로 자동으로 진행됩니다
- 진행 중인 요청은 움직이는 빨간 화살표, 일하는 컴포넌트는 주황 테두리로 표시되고 Pod 상태가 단계별로 바뀝니다

## draw.io 버전 여는 방법

1. https://app.diagrams.net 접속 → `File > Open from > Device` → `pod-creation-flow.drawio` 선택
   (또는 VS Code 의 *Draw.io Integration* 확장으로 바로 열기)
2. 화면 아래의 페이지 탭(`전체 흐름`, `0. 노드 준비`, `1. kubectl 요청`, …)을 순서대로 클릭
3. 화살표 애니메이션은 편집 화면과 `File > Publish / Embed` 뷰어에서 모두 움직입니다.

## 시나리오

```yaml
# nginx-deploy.yaml  →  kubectl apply -f nginx-deploy.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx
spec:
  replicas: 6
  selector:
    matchLabels: { app: nginx }
  template:
    metadata:
      labels: { app: nginx }
    spec:
      containers:
        - name: nginx
          image: nginx
```

## 단계 요약

| 단계 | 누가 | 무엇을 | etcd 상태 |
|---|---|---|---|
| ⓪ (사전) | cloud-controller-manager | 새 Node 를 GCP Compute Engine API 로 조회 → providerID·zone 라벨 기록, uninitialized taint 제거 | Node×3 Ready |
| ① | kubectl | kubeconfig 로 인증 정보를 읽고 API Server 에 `POST deployments` | – |
| ② | kube-apiserver | 인증 → 인가(RBAC) → Mutating Admission → 스키마 검증 → Validating Admission | – |
| ③ | kube-apiserver → etcd | Deployment 저장, kubectl 에 `201 Created` 응답 (**이때 Pod 는 0개**) | Deployment |
| ④ | Deployment Controller | Deployment 를 watch → ReplicaSet(replicas 6) 생성 | + ReplicaSet |
| ⑤ | ReplicaSet Controller | desired 6 / current 0 → Pod 오브젝트 6개 생성 (`nodeName` 비어 있음, Pending) | + Pod×6 (미배정) |
| ⑥ | kube-scheduler | Filtering → Scoring → Binding, Pod 마다 `nodeName` 기록 | Pod×6 (배정됨) |
| ⑦ | kubelet (각 노드) | 자기 노드에 배정된 Pod 를 watch 로 감지 | – |
| ⑧ | kubelet → CRI / CNI / CSI | pause 샌드박스 생성, Pod IP 할당, 이미지 pull, 컨테이너 시작 | ContainerCreating |
| ⑨ | kubelet → kube-apiserver | 상태 보고(Running / Ready) → Deployment 6/6 AVAILABLE | Running 6/6 |
| ⑩ (확장) | cloud-controller-manager | `kubectl expose --type=LoadBalancer` → GCP Load Balancer·방화벽 생성, EXTERNAL-IP 기록 | + Service, EndpointSlice |

**핵심 포인트**

- 컴포넌트끼리 직접 통신하지 않습니다. 모든 읽기/쓰기는 **kube-apiserver 를 거치고**, 상태는 **etcd** 에만 저장됩니다.
- 클라우드(GCP) API 를 호출하는 것은 **cloud-controller-manager 뿐**입니다. kube-controller-manager 는 클라우드를 모릅니다.
- 각 컨트롤러·스케줄러·kubelet 은 API Server 를 **watch** 하다가 *원하는 상태*와 *현재 상태*의 차이를 메우는 **Reconciliation Loop** 로 동작합니다.
- `kubectl` 은 ③ 에서 이미 끝납니다. 이후의 Pod 생성은 클러스터가 **비동기**로 처리합니다
  (`kubectl get pods -w` 로 Pending → ContainerCreating → Running 변화를 직접 확인해 보세요).
- Pod 하나가 죽으면 ReplicaSet Controller 가 차이(5/6)를 감지하고 ⑤ 부터 다시 반복합니다(자가 치유).

## 다이어그램 수정

두 파일 모두 `generate.py` 의 단계 데이터(`STEPS`)로 생성됩니다. 단계 설명이나 배치를 바꾸려면 스크립트를 수정한 뒤 다시 실행하세요.

```bash
python3 generate.py        # → pod-creation-flow.drawio
python3 generate_html.py   # → pod-creation-flow.html
```
