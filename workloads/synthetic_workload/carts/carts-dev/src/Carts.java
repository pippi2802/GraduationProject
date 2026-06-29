import com.jpe.*;

import edu.penn.rtg.schedulingapp.CmdAnal;

import edu.penn.rtg.csa.cadmpr.CADMPRAnalysis;
import edu.penn.rtg.csa.dmpr.DMPRAnalysis;
import edu.penn.rtg.csa.mpr2.MPR2Analysis;

public class Carts {
	public static void main(String args[]) {
		//command: Carts input.xml(args[0]) model(args[1]) output.xml(args[2])
		if (args.length >= 1) { // not call GUI
			if(args[1].toUpperCase().equals("PRM") || args[1].toUpperCase().equals("EDP") || // args[1].toUpperCase().equals("DPRM") ||
				args[1].toUpperCase().equals("EQV")){
				CmdAnal.process(args); 
				return;
			} 
			
			if(args[1].toUpperCase().equals("MPR2") || args[1].toUpperCase().equals("MPR")
					|| args[1].toUpperCase().equals("MPR2_MENG") || args[1].toUpperCase().equals("MPR_MENG")){
				MPR2Analysis.process(args);
				System.out.println("Process  CSA with MPR2 model finished!");
				return; 
			} 
			
			//MPR2hEDF model is based on MPR model. It fixes the interface transformation to Arvind's definition, i.e.,
			if(args[1].equalsIgnoreCase("DMPR") || args[1].equalsIgnoreCase("MPR2hEDF")){
				DMPRAnalysis.process(args);
				System.out.println("Process CSA with DMPR model finished!");
				return;
			}
			
			if(args[1].equalsIgnoreCase("CADMPR_TASKCENTRIC")  
					|| args[1].equalsIgnoreCase("CADMPR_TASKCENTRIC_UB") 
					|| args[1].equalsIgnoreCase("CADMPR_MODELCENTRIC")
					|| args[1].equalsIgnoreCase("CADMPR_HYBRID")
					|| args[1].equalsIgnoreCase("CAMPR2hEDF_TASKCENTRIC") 
					|| args[1].equalsIgnoreCase("CAMPR2hEDF_TASKCENTRIC_UB") 
					|| args[1].equalsIgnoreCase("CAMPR2hEDF_MODELCENTRIC")
					|| args[1].equalsIgnoreCase("CAMPR2hEDF_HYBRID")
					|| args[1].equalsIgnoreCase("CADMPR_TASKCENTRIC_USEMAXOH")  
					|| args[1].equalsIgnoreCase("CADMPR_TASKCENTRIC_UB_USEMAXOH") 
					|| args[1].equalsIgnoreCase("CADMPR_MODELCENTRIC_USEMAXOH")
					|| args[1].equalsIgnoreCase("CADMPR_HYBRID_USEMAXOH")
					|| args[1].equalsIgnoreCase("CAMPR2hEDF_TASKCENTRIC_USEMAXOH") 
					|| args[1].equalsIgnoreCase("CAMPR2hEDF_TASKCENTRIC_UB_USEMAXOH") 
					|| args[1].equalsIgnoreCase("CAMPR2hEDF_MODELCENTRIC_USEMAXOH")
					|| args[1].equalsIgnoreCase("CAMPR2hEDF_HYBRID_USEMAXOH")){
				CADMPRAnalysis.process(args);
				System.out.println("Process CSA with CADMPR_TASKCENTRIC, or CADMPR_TASKCENTRIC_UB, or CADMPR_MODELCENTRIC (Cache Aware DMPR model with Hybrid global EDF) model finished!");
				return;
			}
			
			
			
			System.err.println("Input the wrong resource model!");
			System.err.println("Only support " + "PRM / EDP / EQV / MPR / MPR_Meng / DMPR / CADMPR_TASKCENTRIC / CADMPR_MODELCENTRIC / CADMPR_HYBRID" + " resource models" );
				
		} else { //call GUI
			jpe.main(args);
		}
	}
	
	
}
