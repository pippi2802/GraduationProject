package edu.penn.rtg.csa.cadmpr;

import edu.penn.rtg.common.*;

/**
 * Class CAMPR2hEDFAnalysis
 * It's the start point of the cache aware MPR analysis
 * It parse the input xml file, call the Component.java to analysis the system recursively and 
 * output the result to output xml file.
 * 
 * JDK version used: <JDK1.7>
 * @author Meng Xu
 * Create Date: 4/6/2013 
 *
 */
public class CADMPRAnalysis {
	public static void process(String[] args){
		if(args.length < 3){
			error();
		}
		
		try{
			int whichSchedTest = -1;
			if(args.length == 3){
				//DEFAULT SCHED TEST!
				whichSchedTest = GlobalVariable.ARVIND_SCHEDTEST; //ARVIND_SCHEDTEST;//BERTOGNA_SCHEDTEST
				
			}else if(args.length >= 4){ // >= to make it easier in eclipse to debug.
				whichSchedTest = parseWhichSchedTest(args[3]);
				
			}
			System.out.println("Command is:" + args[0] + " " + args[1] + " " + args[2] + " whichSchedTest="+ whichSchedTest);
			
			boolean useMaxOh = false;
			if(args[1].contains("USEMAXOH")){
				useMaxOh = true;
			}
			
			String resourceModel = "";
			int whichApproach = -1;
			if(args[1].equalsIgnoreCase("CAMPR2hEDF_TASKCENTRIC") || args[1].equalsIgnoreCase("CADMPR_TASKCENTRIC")
					|| args[1].equalsIgnoreCase("CAMPR2hEDF_TASKCENTRIC_USEMAXOH") || args[1].equalsIgnoreCase("CADMPR_TASKCENTRIC_USEMAXOH")){
				System.out.println("Using Task Centric overhead accounting technique");
				resourceModel = "CAMPR2hEDF_TASKCENTRIC";
				whichApproach = GlobalVariable.TASK_CENTRIC;
			}else if(args[1].equalsIgnoreCase("CAMPR2hEDF_TASKCENTRIC_UB") || args[1].equalsIgnoreCase("CADMPR_TASKCENTRIC_UB")
					||args[1].equalsIgnoreCase("CAMPR2hEDF_TASKCENTRIC_UB_USEMAXOH") || args[1].equalsIgnoreCase("CADMPR_TASKCENTRIC_UB_USEMAXOH")){
				System.out.println("Using Task Centric Upper Bound overhead accounting technique");
				resourceModel = "CAMPR2hEDF_TASKCENTRIC_UB";
				whichApproach = GlobalVariable.TASK_CENTRIC_UB;
			}else if(args[1].equalsIgnoreCase("CAMPR2hEDF_MODELCENTRIC") || args[1].equalsIgnoreCase("CADMPR_MODELCENTRIC")
					||args[1].equalsIgnoreCase("CAMPR2hEDF_MODELCENTRIC_USEMAXOH") || args[1].equalsIgnoreCase("CADMPR_MODELCENTRIC_USEMAXOH")){
				System.out.println("Using Model Centric overhead accounting technique");
				resourceModel = "CAMPR2hEDF_MODELCENTRIC";
				whichApproach = GlobalVariable.MODEL_CENTRIC;
			}else if(args[1].equalsIgnoreCase("CADMPR_HYBRID") || args[1].equalsIgnoreCase("CAMPR2hEDF_HYBRID")
					||args[1].equalsIgnoreCase("CADMPR_HYBRID_USEMAXOH") || args[1].equalsIgnoreCase("CAMPR2hEDF_HYBRID_USEMAXOH")){
				resourceModel = "CADMPR_HYBRID";
				whichApproach = GlobalVariable.HYBRID;
			}else{
				System.out.println("No such analysis approach, please check the analysis approach: " + args[1] + "\r\n exit(1)");
				System.exit(1);
			}
			
			run(args[0],resourceModel, args[2], whichApproach, whichSchedTest, useMaxOh);
			
		}catch(Exception e){
			e.printStackTrace();
			System.err.println("Exception trown out in the analysis");
		}
	}
	
	/*Note: CADMPR only supports two level scheduling right now! Although it can run for multiple level scheduling, the result's correctness is not checked!*/
	public static void run(String inputFilename, String resourceModel, String outputFilename,int whichApproach, int whichSchedTest, boolean useMaxOh ){

		XMLInterpreter4CADMPR xmlInterpreter = new XMLInterpreter4CADMPR(inputFilename); //4 is short for "for"
		
		xmlInterpreter.parseFile();
		Component rootComponent = xmlInterpreter.getRootComponent();
		
		//reset the crpmd = 1.9ms which is the crpmd cost when task set WSS is 256KB. Only to walk around when delta_crpmd is wrongly set in input xml
		//rootComponent.resetDelta_crpmd();
		double maxOh = 0;
		if(useMaxOh == true){
			maxOh = rootComponent.getMaxOhInSystem();
		}
		
		switch(whichApproach){
		case GlobalVariable.TASK_CENTRIC: doCADMPRTaskCentricAnalysis(rootComponent, whichApproach, whichSchedTest, useMaxOh, maxOh); break;
		case GlobalVariable.TASK_CENTRIC_UB: doCADMPRTaskCentricUBAnalysis(rootComponent, whichApproach, whichSchedTest, useMaxOh, maxOh); break;
		case GlobalVariable.MODEL_CENTRIC: doCADMPRModelCentricAnalysis(rootComponent, whichApproach, whichSchedTest, useMaxOh, maxOh); break;
		case GlobalVariable.HYBRID: rootComponent = doCADMPRHybridAnalysis(rootComponent, whichApproach, whichSchedTest, useMaxOh, maxOh); break;
		default: System.err.println("No such overhead aware MPR analysis approach. Only suport TaskCentri and ModelCentric approach now. Exit(1)"); System.exit(1);
		}
				
		XMLWriter4CADMPR xmlWriter = new XMLWriter4CADMPR(outputFilename, rootComponent);
		
		xmlWriter.writeComponentInterfaceTree(whichApproach);
		
	}
	
	public static int parseWhichSchedTest(String str){
		if(str.equalsIgnoreCase("ARVIND_SCHEDTEST")) return GlobalVariable.ARVIND_SCHEDTEST;
		if(str.equalsIgnoreCase("BERTOGNA_SCHEDTEST")) return GlobalVariable.BERTOGNA_SCHEDTEST;
		if(str.equalsIgnoreCase("ARVIND_SCHEDTEST_FAST")) return GlobalVariable.ARVIND_SCHEDTEST_FAST;
		if(str.equalsIgnoreCase("MENG_SCHEDTEST")) return GlobalVariable.MENG_SCHEDTEST;
		
		System.err.println("In parseWhichSchedTest() No such sched test! System exit.");
		System.exit(1);
		return 0;
	}
	
	private static void error() {
		System.err.println("Invalid arguments");
		System.err
				.println("Carts <input_XML_file> <scheduling_algo> <output_XML_file>");
		System.err
		.println("<scheduling_algo> can be : PRM / EDP / EQV / MPR (MPR2) / DMPR / " +
				"CADMPR_TASKCENTRIC (CAMPR2hEDF_TASKCENTRIC) / CADMPR_MODELCENTRIC (CAMPR2hEDF_MODELCENTRIC) / " +
				"CADMPR_HYBRID (CAMPR2hEDF_HYBRID)");
		System.exit(1);
		
	}
	
	public static String doCADMPRTaskCentricAnalysis(Component rootComponent, int whichApproach, int whichSchedTest, boolean useMaxOh, double maxOh){
		String result = checkSchedulingAlgorithm(rootComponent);
		rootComponent.inflateTaskWCET_taskCentric(useMaxOh, maxOh);
		rootComponent.doCSA(whichSchedTest, whichApproach);
		return result;
	}
	
	public static String doCADMPRTaskCentricUBAnalysis(Component rootComponent, int whichApproach, int whichSchedTest, boolean useMaxOh, double maxOh){
		String result = checkSchedulingAlgorithm(rootComponent);
		rootComponent.inflateTaskWCETEV1_Bjorn(useMaxOh, maxOh);
		rootComponent.doCSA(whichSchedTest, GlobalVariable.TASK_CENTRIC);
	
		rootComponent.set_taskcentricUBOnly_interface_and_interfacetasks_for_all_leaf(); //set interface upper bound
		//clear the dMPRInterface to performance task centric analysis again and compare with the interface upper bound calculated above
		rootComponent.clear_cadmpr_interface_and_interfacetasks_for_all_nodes();
		
		rootComponent.inflateTaskWCET_onlyVCPUEvent(useMaxOh, maxOh);
		rootComponent.doCSA(whichSchedTest, GlobalVariable.TASK_CENTRIC_UB); /*when compute leaf component, need compare with interface upper bound*/
		
		return result; 
	}
	
	public static String doCADMPRModelCentricAnalysis(Component rootComponent, int whichApproach, int whichSchedTest,boolean useMaxOh, double maxOh){
		String result = checkSchedulingAlgorithm(rootComponent);
		rootComponent.inflateTaskWCETEV1_Bjorn(useMaxOh, maxOh);
		rootComponent.doCSA(whichSchedTest, whichApproach);
		return result;
	}
	
	public static Component doCADMPRHybridAnalysis(Component rootComponent, int whichApproach, int whichSchedTest,boolean useMaxOh, double maxOh){
		//check scheduling algorithm, which must be hybrid EDF(i.e., gEDF, hEDF, EDF in input xml)
		String result_hybrid = checkSchedulingAlgorithm(rootComponent);
		if(!result_hybrid.contains("SUCCESS")){
			rootComponent.setInterfaceComputed(false);
			return rootComponent;
		}
		
		Component component_taskcentric = new Component(rootComponent, null);	
		String result_taskcentric = doCADMPRTaskCentricAnalysis(component_taskcentric,GlobalVariable.TASK_CENTRIC, whichSchedTest, useMaxOh, maxOh );
	
		Component component_modelcentric = new Component(rootComponent, null);
		String result_modelcentric = doCADMPRModelCentricAnalysis(component_modelcentric, GlobalVariable.MODEL_CENTRIC, whichSchedTest, useMaxOh, maxOh);
		
		CADMPR cadmpr_taskcentric = component_taskcentric.getCacheAwareMPRInterface();
		CADMPR cadmpr_modelcentric = component_modelcentric.getCacheAwareMPRInterface();
		double totalBudget_taskcentric = cadmpr_taskcentric.getPi()*cadmpr_taskcentric.getM_dedicatedCores() 
							+ cadmpr_taskcentric.getTheta();
		double totalBudget_modelcentric = cadmpr_modelcentric.getPi()*cadmpr_modelcentric.getM_dedicatedCores()
							+ cadmpr_modelcentric.getTheta();
		
		//return the root component which has the result of Hybrid approach
		if(totalBudget_taskcentric <= totalBudget_modelcentric){
			return new Component(component_taskcentric,null);
		}else{
			return new Component(component_modelcentric, null);
		}

	}
	
	public static String checkSchedulingAlgorithm(Component rootComponent){
		String result = "";
		if (!(rootComponent.getSchedulingPolicy().equalsIgnoreCase("hEDF")
				|| rootComponent.getSchedulingPolicy().equalsIgnoreCase("EDF") || rootComponent
				.getSchedulingPolicy().equalsIgnoreCase("gEDF"))) {
			System.err.println("ERROR: only support hEDF scheduling policy in each component with CADMPR model");
			return "ERROR: only support hEDF scheduling policy in each component with CADMPR model";
		}
		for (Component component : rootComponent.getChildComponents()) {
			// EDF is considered as gEDF by default
			String child_result = checkSchedulingAlgorithm(component);
			if(!child_result.contains("SUCCESS")){
				return child_result;
			}
			
		}

		return "SUCCESS!";
	}

}
