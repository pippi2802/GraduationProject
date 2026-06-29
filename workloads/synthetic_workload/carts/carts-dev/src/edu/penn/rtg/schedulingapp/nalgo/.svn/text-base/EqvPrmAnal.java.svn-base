package edu.penn.rtg.schedulingapp.nalgo;

import java.util.Vector;
import edu.penn.rtg.schedulingapp.basic.*;

public class EqvPrmAnal {
    public static void analysis(SComponent comp) {
        Vector<SComponent> comList = comp.getComList();
             
        if(comList != null) {
            EqvPrmModel eqvRm = new EqvPrmModel();
            
            for (SComponent c : comList) {
                EqvPrmAnal.analysis(c);
                EqvPrmModel rmc = (EqvPrmModel) c.getResModel();
                eqvRm = EqvPrmModel.compose(eqvRm, rmc);
            }
            
            comp.setResModel(eqvRm);
            comp.setEqvRes(eqvRm);
            
        }else {
            EqvPrmEDF eqvPrm = new EqvPrmEDF(comp.getWorkload());
            eqvPrm.setPeriodLimit(comp.getPeriodLimit());
            comp.setInitRes(eqvPrm.getInitRes());
            EqvPrmModel eqvRm = (EqvPrmModel) eqvPrm.getRes();
            comp.setResModel(eqvRm);
            comp.setEqvRes(eqvRm);
        }
    }
    
    public static void finalizePeriod(SComponent comp, int period) {
        Vector<SComponent> comList = comp.getComList();
        
        if(comList != null) {
            if(period < 0) {
                EqvPrmModel eqvPrm = (EqvPrmModel) comp.getResModel();
                
                int periodByRoot = 0;
                if(eqvPrm.periodSet.discSet.size() > 0) {
                    periodByRoot = eqvPrm.periodSet.discSet.get(eqvPrm.periodSet.discSet.size() - 1);
                }else {
                    periodByRoot = (int) Math.ceil(eqvPrm.periodSet.contBound);
                }
                
                PeriodicRM rm = new PeriodicRM(periodByRoot, eqvPrm.bandwidth*periodByRoot);
                comp.setResModel(rm);
                
                for(SComponent c : comList) {
                    EqvPrmAnal.finalizePeriod(c, periodByRoot);
                }
            }else {
                EqvPrmModel eqvPrm = (EqvPrmModel) comp.getResModel();
                PeriodicRM rm = new PeriodicRM(period, eqvPrm.bandwidth*period);
                comp.setResModel(rm);
                
                for(SComponent c : comList) {
                    EqvPrmAnal.finalizePeriod(c, period);
                }
            }
        }else {
            if(period == -1) {
                EqvPrmModel eqvPrm = (EqvPrmModel) comp.getResModel();
                
                int periodByRoot = 0;
                if(eqvPrm.periodSet.discSet.size() > 0) {
                    periodByRoot = eqvPrm.periodSet.discSet.get(eqvPrm.periodSet.discSet.size() - 1);
                }else {
                    periodByRoot = (int) Math.ceil(eqvPrm.periodSet.contBound);
                }
                
                PeriodicRM rm = new PeriodicRM(periodByRoot, eqvPrm.bandwidth*periodByRoot);
                comp.setResModel(rm);
                
            }else {
                EqvPrmModel eqvPrm = (EqvPrmModel) comp.getResModel();
                PeriodicRM rm = new PeriodicRM(period, eqvPrm.bandwidth*period);
                comp.setResModel(rm);
            }
        }
    }

}
