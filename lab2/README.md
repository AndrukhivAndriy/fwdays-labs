# Module 03 — Platform Engineering: GitOps + Helm + Kyverno

> **Результат: виконано.** Kyverno-політики описані окремим Helm chart, а їхнім бажаним станом керує Argo CD з Git-репозиторію. Підтверджений фінальний стан Application: **Healthy / Synced**.


## 1. Архітектура

```text
GitHub: AndrukhivAndriy/fwdays-labs (branch: dev)
                    │
                    ▼
           Argo CD Application
             fwdays-policies
                    │
                    ▼
            Helm chart: lab2/
                    │
          ┌─────────┴─────────┐
          ▼                   ▼
   Mutation Policy      Validation Policy
   person label         readonlyRootfs (Audit)
          └─────────┬─────────┘
                    ▼
              Kyverno / k3s
```


## 2. Helm chart: політики

### 2.1. Mutation — `fwdays-policies-person-label`

Для Pod у namespace з міткою `person-role=student` автоматично додається `person=student`; для `person-role=mentor` — `person=mentor`. Використано `namespaceSelector`, тому правила не залежать від конкретних імен студентів чи namespaces.

### 2.2. Validation — `fwdays-policies-readonly-rootfs`

Для Pod у namespaces з `person-role=student` або `person-role=mentor` перевіряється `securityContext.readOnlyRootFilesystem: true` у звичайних та init-контейнерах. Режим **Audit**: порушення реєструються, але створення Pod не блокується.

Обидві політики використовують API `kyverno.io/v1`, тип `ClusterPolicy`. У шаблонах явно задано стандартні поля Kyverno (`admission`, `emitWarning`, `validationFailureAction`, `skipBackgroundRequests`, `allowExistingViolations`), щоб уникнути постійного `OutOfSync` після нормалізації ресурсів контролером.


## 3. Підключення до Argo CD

Параметри Application:

| Поле | Значення |
| --- | --- |
| Application | `fwdays-policies` |
| Project | `default` |
| Repository | `https://github.com/AndrukhivAndriy/fwdays-labs.git` |
| Target revision | `dev` |
| Path | `lab2` |
| Helm release name | `fwdays-policies` |
| Destination | `in-cluster`, namespace `default` |
| Sync policy | `automated`, `prune`, `selfHeal` |

Команди для відтворення конфігурації (не потрібно запускати повторно у вже налаштованому кластері):

```bash
helm lint lab2 && helm template fwdays-policies lab2
kubectl apply -f lab2/argocd/application.yaml
kubectl -n argocd get application fwdays-policies
kubectl get clusterpolicy fwdays-policies-person-label fwdays-policies-readonly-rootfs
```

## 4. Скриншоти виконання

### 4.1. Argo CD встановлено — початковий стан

Інтерфейс Argo CD v3.5.5 до створення Application.

![Argo CD — до створення Application](screenshots/argocd-before-application.png)

### 4.2. Argo CD — фінальний стан Healthy / Synced

Application `fwdays-policies`: Git revision `dev`, шлях `lab2`, destination `in-cluster`, **Healthy / Synced**.

![Argo CD — Healthy і Synced](screenshots/argocd-synced-healthy.png)
