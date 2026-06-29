package edu.penn.rtg.schedulingapp.nalgo;

import java.util.*;

/**
 * This defines a period set that is used by equivalent period interface's bandwidth-periods representation
 * The basic structure of a period set is PeriodSet = {0, contBound} U {a discrete set}
 * @author Sanjian Chen
 *
 */
public class PeriodSet {
    public double contBound;
    public ArrayList<Integer> discSet;
    
    public PeriodSet() {
        this.contBound = 0;
        this.discSet = new ArrayList<Integer>();
        Collections.sort(this.discSet);
    }
    
    /**
     * Construct directly by given bound and discSet
     * @param contBound
     * @param discSet
     */
    public PeriodSet(double contBound, ArrayList<Integer> discSet) {
        this.contBound = contBound;
        this.discSet = discSet;
        Collections.sort(this.discSet);
    }
    
    /**
     * Given the original period, construct the set using the Gamma function defined in RTAS'11 Chen's paper
     * @param period
     */
    public PeriodSet(long period) {
        this.contBound = (double) period / 2;
        
        this.discSet = new ArrayList<Integer>();
        for(long k = 0; k <= (double)(period - 1)/2; k++) {
            if(period % (2*k+1) == 0) {
                double temp = (double) period * (k + 1) / (2*k + 1);
//                System.out.println(k + " : " + (int)temp);
                this.discSet.add((int) temp);
            }
        }
        
        Collections.sort(this.discSet);
    }
    
    public static PeriodSet intersect(PeriodSet set1, PeriodSet set2) {
        PeriodSet intersection = new PeriodSet();
        
        PeriodSet small = new PeriodSet();
        PeriodSet large = new PeriodSet();
        
        if(set1.contBound <= set2.contBound) {
            small = set1;
            large = set2;
        }else {
            small = set2;
            large = set1;
        }
        
        intersection.contBound = small.contBound;
        
        Collections.sort(small.discSet);
        Collections.sort(large.discSet);
        ArrayList<Integer> common = new ArrayList<Integer>();
        
        int j = 0;
        for(int i = 0; i < small.discSet.size(); i++) {
            if(small.discSet.get(i) <= large.contBound) {
                common.add(small.discSet.get(i));
            }else {
                while(j < large.discSet.size() && small.discSet.get(i) >= large.discSet.get(j)) {
                    if(small.discSet.get(i) == large.discSet.get(j)) {
                        common.add(small.discSet.get(i));
                    }
                    j++;
                }
            }
        }
        
        intersection.discSet = common;
        
        return intersection;
    }
    
    public void printMyself() {
        System.out.println("Bound: " + this.contBound);
        for(int i = 0; i < this.discSet.size(); i++) {
            System.out.println("Set Element " + i + " : " + this.discSet.get(i));
        }
    }

}
