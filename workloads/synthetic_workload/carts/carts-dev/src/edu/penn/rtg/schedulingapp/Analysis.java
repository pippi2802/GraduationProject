package edu.penn.rtg.schedulingapp;



import edu.penn.rtg.schedulingapp.algo.EQVPRM;
import edu.penn.rtg.schedulingapp.algo.MPR;
import edu.penn.rtg.schedulingapp.algo.Sirap;
import edu.penn.rtg.schedulingapp.algo.ARINC;
import edu.penn.rtg.schedulingapp.algo.EDP;
import edu.penn.rtg.schedulingapp.algo.DPRM;
import edu.penn.rtg.schedulingapp.algo.Periodic;
import edu.penn.rtg.schedulingapp.util.UserUtil;
/**
 * Analyze component with specific resource model
 */
public class Analysis {
	public static String preProcess(String algo,TreeComponent comp) throws Exception 
	{
		if(algo.equals("PRM")) {
			return preProcessPRM(comp);
		} else if(algo.equals("EDP")) {
			return preProcessEDP(comp);
		} else if(algo.equals("DPRM")) {
			processDPRM(comp);
			return "DPRM interface";
		} else if(algo.equals("MPR")) {
			processMPR(comp);
			return "MPR interface";
		} else if(algo.equals("EQV")) {
			processEQV(comp);
			return "EQV interface";
		}
		return "ERR";
	}
	public static String preProcessPRM(TreeComponent comp) throws Exception {
		String ret=Sirap.check(comp);
		//System.out.println(ret);
		if(ret.equals("SIRAP")) {	// Process Sirap
			processSIRAP(comp);
			return "PRM interface (SIRAP algorithm)";
		}
		if(ret.equals("PRM")) { // process Periodic
			processPRM(comp);
			return "PRM interface";
		}
		if(ret.equals("ARINC")) {
			ret="jitter,offset cannot be applied with PRM interface";
			ret+="\n Do you want continue to process with PRM? ";
			int t=UserUtil.answerYN(ret, "Cannot process with PRM");
			if(t==0) {	
				processPRM(comp);
				return "PRM interface (jitter, offset is ignored)";
			} else {
				return null;
			}
		}
		// Error message,  Process Periodic (cs is ignored) 
		ret+="\n Do you want continue to process with PRM? ";
		int t=UserUtil.answerYN(ret, "Cannot process with PRM");
		if(t==0) {	
			processPRM(comp);
			return "PRM interface (cs is ignored)";
		} else {
			return null;
		}


	}
	public static String preProcessEDP(TreeComponent comp) throws Exception {
		String ret=ARINC.check(comp);
		if(ret.equals("ARINC")) {
			processArinc(comp);
			return "EDP interface (with Arinc task)";
		}
		if(ret.equals("EDP")) {
			processEDP(comp);
			return "EDP interface";
		}
		else if(ret.equals("SIRAP")){
			ret="critcal section cannot be applied with EDP interface";
			ret+="\n Do you want continue to process with EDP? ";
			int t=UserUtil.answerYN(ret, "Cannot process with EDP");
			if(t==0) {	
				processEDP(comp);
				return "EDP interface (cs is igonored)";
			} else {
				return null;
			}
		}
		// Error message,  Process EDP
		ret+="\n Do you want continue to process with EDP? ";
		int t=UserUtil.answerYN(ret, "Cannot process with EDP");
		if(t==0) {	
			processEDP(comp);
			return "EDP interface (jitter,offset is igonored)";
		} else {
			return null;
		}

	}
	/**
	 * Process the system with Periodic Algorithm
	 * 
	 * @param comp
	 *            SchedulingComponent to which the algorithm needs to be applied
	 * @throws Exception
	 *             If any mismatch is found between the field values of
	 *             components and tasks and the algorithm, an exception will be
	 *             thrown
	 */
	public static void processPRM(TreeComponent comp) throws Exception {
		Periodic toGo = new Periodic();
		toGo.start(comp);
		try{
			comp.getSchCom().setRevised(true);
			toGo.abstractionProcedure(comp);
			comp.setProcessed(true);
		}
		catch(OutOfMemoryError e)
		{
			UserUtil.showErr("OutOfMemoryError: Java heap space");
			comp.setProcessed(false);
		}
		comp.getSchCom().setProcAlgoRecur("PRM");
		toGo.end();
	}

	/**
	 * Process the system with EDP Algorithm
	 * 
	 * @param comp
	 *            SchedulingComponent to which the algorithm needs to be applied
	 * @throws Exception
	 *             If any mismatch is found between the field values of
	 *             components and tasks and the algorithm, an exception will be
	 *             thrown
	 */
	public static void processEDP(TreeComponent comp) throws Exception {
		EDP toGo = new EDP();
		toGo.start(comp);
		try{
			comp.getSchCom().setRevised(true);
			toGo.abstractionProcedure(comp);
			comp.setProcessed(true);
		}
		catch(OutOfMemoryError e)
		{
			UserUtil.showErr("OutOfMemoryError: Java heap space");
			comp.setProcessed(false);
		}
		comp.getSchCom().setProcAlgoRecur("EDP");
		toGo.end();
	}

	/**
	 * Process the system with ARINC Algorithm
	 * 
	 * @param comp
	 *            SchedulingComponent to which the algorithm needs to be applied
	 * @throws Exception
	 *             If any mismatch is found between the field values of
	 *             components and tasks and the algorithm, an exception will be
	 *             thrown
	 */
	public static void processArinc(TreeComponent comp) throws Exception {
		ARINC toGo = new ARINC();
		toGo.start(comp);
		try{
			comp.getSchCom().setRevised(true);
			toGo.abstractionProcedure(comp);
			comp.setProcessed(true);
		}
		catch(OutOfMemoryError e)
		{
			UserUtil.showErr("OutOfMemoryError: Java heap space");
			comp.setProcessed(false);
		}
		comp.getSchCom().setProcAlgoRecur("ARINC");
		toGo.end();
	}
	/**
	 * Process the system with SIRAP Algorithm
	 * 
	 * @param comp
	 *            SchedulingComponent to which the algorithm needs to be applied
	 */
	public static void processSIRAP(TreeComponent comp) throws Exception {
		Sirap toGo = new Sirap();
		toGo.start(comp);
		try{
			comp.getSchCom().setRevised(true);
			toGo.abstractionProcedure(comp);
			comp.setProcessed(true);
		}
		catch(OutOfMemoryError e)
		{
			UserUtil.showErr("OutOfMemoryError: Java heap space");
			comp.setProcessed(false);
		}
		comp.getSchCom().setProcAlgoRecur("SIRAP");
		toGo.end();
	}

	/**
	 * Process the system with DPRM Interface
	 * 
	 * @param comp
	 *            SchedulingComponent to which the algorithm needs to be applied
	 */
	public static void processDPRM(TreeComponent comp) throws Exception {
		if(!DPRM.check(comp)) {
			UserUtil.showErr("Computing DPRM interface only works with EDF. Cannot continue");
			return;
		}
		DPRM toGo = new DPRM();
		toGo.start(comp);
		try{
			comp.getSchCom().setRevised(true);
			toGo.abstractionProcedure(comp);
			comp.setProcessed(true);
		}
		catch(OutOfMemoryError e)
		{
			UserUtil.showErr("OutOfMemoryError: Java heap space");
			comp.setProcessed(false);
		}
		comp.getSchCom().setProcAlgoRecur("DPRM");
		toGo.end();
	}

	/**
	 * Process the system with MPR Interface
	 * 
	 * @param comp
	 *            SchedulingComponent to which the algorithm needs to be applied
	 */
	public static void processMPR(TreeComponent comp) throws Exception {
		if(!MPR.check(comp)) {
			UserUtil.showErr("Computing MPR interface only works with EDF. Cannot continue");
			return;
		}
		
		MPR toGo = new MPR();
		toGo.start(comp);
		try{
			comp.getSchCom().setRevised(true);
			toGo.abstractionProcedure(comp); //abstract the task set/children components to interface via recursion.
			comp.setProcessed(true);
		}
		catch(OutOfMemoryError e) {
			UserUtil.showErr("OutOfMemoryError: Java heap space");
			comp.setProcessed(false);
		}
		comp.getSchCom().setProcAlgoRecur("MPR");
		toGo.end();
	}
	public static void processEQV(TreeComponent comp) throws Exception {
		if(!EQVPRM.check(comp)) {
			UserUtil.showErr("Computing EQV interface only works with EDF. Cannot continue");
			return;
		}
		EQVPRM toGo = new EQVPRM(comp);
		try{
			comp.getSchCom().setRevised(true);
			toGo.run();
			comp.setProcessed(true);
		}
		catch(OutOfMemoryError e)
		{
			UserUtil.showErr("OutOfMemoryError: Java heap space");
			comp.setProcessed(false);
		}
		comp.getSchCom().setProcAlgoRecur("EQV");
	}
}
