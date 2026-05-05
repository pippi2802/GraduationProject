#include <stdio.h>
#include <stdlib.h>

int main(int argc, char *argv[])
{
    int dl = 0, dlmiss = -1;
    int res, lastv;
    int value, num;
    float prob, lastp = 0;

    if (argc > 1) {
        dl = atoi(argv[1]);
    }
    if (dl <= 0) {
        fprintf(stderr, "Please provide a deadline!\n");
    }
    
    while(!feof(stdin)) {
        res = scanf("%d %d %f\n", &value, &num, &prob);
        if (res == 3) {
            if ((value > dl) && (dlmiss == -1)) {
                dlmiss = lastv;
                fprintf(stderr, "Dl miss probability: %f\n", 1 - lastp);
            }
            lastv = num;
            lastp = prob;
        }
    }

    if (dlmiss == -1) {
        dlmiss = lastv;
    }

    printf("Miss: 1 - %d / %d = %f\n", dlmiss, lastv, 1.0 - ((double)dlmiss / (double)lastv));

    return 0;
}
