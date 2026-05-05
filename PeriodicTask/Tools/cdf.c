#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>

struct list_elem {
    int value;
    int cnt;
    struct list_elem *next;
};

static struct list_elem *list_insert(struct list_elem *l, int value)
{
    struct list_elem *p, *p1, *res;

    p1 = NULL;
    p = l;
    while ((p != NULL) && (p->value <= value)) {
        if (p->value == value) {
            p->cnt++;

            return l;
        }
        p1 = p;
        p = p->next;
    }

    res = malloc(sizeof(struct list_elem));
    if (res == NULL) {
        return NULL;
    }
    res->value = value;
    res->cnt = 1;
    res->next = p;

    if (p1 == NULL) {
        return res;
    }
    p1->next = res;

    return l;
}

static void cdf_print(struct list_elem *l)
{
    int cnt, total;
    struct list_elem *p;

    total = 0;
    p = l;
    while (p != NULL) {
        total += p->cnt;
	p = p->next;
    }

    cnt = 0;
    p = l;
    while (p != NULL) {
        cnt += p->cnt;
        printf("%d %d %f\n", p->value, cnt, (double)cnt / (double)total);
	p = p->next;
    }
}

int main()
{
    int r;
    struct list_elem *h;
    int res;

    h = NULL;
    while(!feof(stdin)) {
        res = scanf("%d\n", &r);
        if (res == 1) {
            h = list_insert(h, r);
        }
    }

    cdf_print(h);
    return 0;
}
