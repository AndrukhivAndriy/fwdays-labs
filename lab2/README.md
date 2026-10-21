# Module 03 — Helm chart для Kyverno policies

Цей Helm chart відокремлює **Kyverno policies** від `lab1` (namespaces, ServiceAccount, RBAC) і дозволяє керувати політиками через **Argo CD / GitOps**.

## Політики

1. `fwdays-policies-readonly-rootfs` — перевіряє `readOnlyRootFilesystem: true` для звичайних та init-контейнерів у namespaces з `person-role=student` або `person-role=mentor`. Режим **Audit**, Pod не блокується.
2. `fwdays-policies-person-label` — додає Pod label `person=student` або `person=mentor` відповідно до мітки namespace.

Список студентів не зашитий у шаблонах: нові namespaces, позначені `person-role=student`, автоматично підпадають під правила.

**Увага:** ці дві політики не забороняють `person` в інших namespaces. Для повного виконання останньої умови Module 02 потрібна окрема validation policy; вона не входить до перенесення наявних двох політик.

## Розгортання через Argo CD

1. Скопіювати папку `lab2/` у корінь публічного репозиторію `fwdays-labs`, гілка `dev`.
2. Перевірити локально: `helm lint lab2 && helm template fwdays-policies lab2`.
3. Додати зміни в Git та виконати push до `dev`.
4. Створити Argo CD Application: `kubectl apply -f lab2/argocd/application.yaml`.
5. Перевірити: `kubectl -n argocd get application fwdays-policies` і `kubectl get clusterpolicies`.

### Безпечна міграція з Module 02

**Не видаляти release `learning-lab`**: він керує namespaces, ServiceAccount та RBAC.

Нові політики мають **інші імена**, тому Argo CD не перезаписуватиме Helm-ресурси Module 02. Спочатку переконайтеся, що нові політики мають `Ready=True`, а Pod у студентському/менторському namespace отримує правильну мітку.

Після перевірки приберіть **лише два шаблони** `lab1/templates/kyverno-validation.yaml` та `lab1/templates/kyverno-mutation.yaml`, і виконайте `helm upgrade learning-lab ./lab1 -n default --wait` (або з каталогу `lab1`: `helm upgrade learning-lab . -n default --wait`). Це прибере старі політики Helm, але збереже namespaces і RBAC. До цього моменту дві групи політик працюватимуть паралельно.

### Перевірка

```bash
kubectl get clusterpolicies
kubectl run m03-student-test --image=nginx:alpine -n student01
kubectl run m03-mentor-test --image=nginx:alpine -n mentor
kubectl get pod m03-student-test -n student01 -o jsonpath='{.metadata.labels.person}{"\n"}'
kubectl get pod m03-mentor-test -n mentor -o jsonpath='{.metadata.labels.person}{"\n"}'
kubectl get policyreports -A
```

Очікується `student`, `mentor`; PolicyReport має зафіксувати порушення readonly root filesystem, не блокуючи створення Pod.

### Примітка щодо Kyverno

Використано **`kyverno.io/v1 ClusterPolicy`**, оскільки цей формат уже підтверджено як робочий у встановленому Kyverno. API deprecated; майбутню міграцію на `policies.kyverno.io` / CEL слід виконувати окремо з перевіркою сумісності.
