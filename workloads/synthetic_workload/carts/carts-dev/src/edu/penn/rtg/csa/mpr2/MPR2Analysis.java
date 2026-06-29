package edu.penn.rtg.csa.mpr2;
import edu.penn.rtg.common.*;

/**
 * Class MPR2Analysis
 * It's the start point of the MPR2 analysis
 * It parse the input xml file, call the Component.java to analysis the system recursively and 
 * output the result to output xml file.
 * 
 * JDK version used: <JDK1.7>
 * @author Meng Xu
 * Create Date: 4/6/2013 
 *
 */
public class MPR2Analysis { 
	public static void process(String[] args){
		if(args.length < 3){
			error();
		}
		
		try{
			if(args.length == 3){
				//DEFAULT SCHED FAST TEST!
				int whichSchedTest = GlobalVariable.ARVIND_SCHEDTEST_FAST; //ARVIND_SCHEDTEST;//BERTOGNA_SCHEDTEST
				int sbf_type = parseSBFType(args[1]);
				System.out.println("Command is:" + args[0] + " " + args[1] + " " + args[2] + " whichSchedTest="+ whichSchedTest);
				run(args[0],args[1],args[2],whichSchedTest, sbf_type);
			}else if(args.length >= 4){ // >= to make it easier in eclipse to debug.
				int whichSchedTest = parseWhichSchedTest(args[3]);
				int sbf_type = parseSBFType(args[1]);
				System.out.println("Using " + args[3] + " sched test!");
				run(args[0],args[1],args[2],whichSchedTest, sbf_type);
			}
			
			
		}catch(Exception e){
			e.printStackTrace();
			System.err.println("Exception trown out in the analysis");
		}
	}
	
	public static void run(String inputFilename, String resourceModel, String outputFilename, int whichSchedTest, int sbf_type){

		XMLInterpreter4MPR2 xmlInterpreter = new XMLInterpreter4MPR2(inputFilename); //4 is short for "for"
		
		xmlInterpreter.parseFile();
		Component rootComponent = xmlInterpreter.getRootComponent();
		
		doCSA_start(rootComponent, whichSchedTest, sbf_type);
		
		
		
		//rootComponent.checkThetaMonotonic(whichSchedTest);//Temporary experiment: check if Theta has monotonic property! comment it when do not need this check!
		
		XMLWriter4MPR2 xmlWriter = new XMLWriter4MPR2(outputFilename, rootComponent);
		xmlWriter.writeComponentInterfaceTree(sbf_type);
		
	}
	
	public static int parseWhichSchedTest(String str){
		if(str.equalsIgnoreCase("ARVIND_SCHEDTEST")) return GlobalVariable.ARVIND_SCHEDTEST;
		//if(str.equalsIgnoreCase("BERTOGNA_SCHEDTEST")) return GlobalVariable.BERTOGNA_SCHEDTEST; //avoid misunderstanding. only use MARKO_SCHEDTEST
		if(str.equalsIgnoreCase("ARVIND_SCHEDTEST_FAST")) return GlobalVariable.ARVIND_SCHEDTEST_FAST;
		if(str.equalsIgnoreCase("MENG_SCHEDTEST")) return GlobalVariable.MENG_SCHEDTEST;
		if(str.equalsIgnoreCase("MARKO_SCHEDTEST")) return GlobalVariable.MARKO_SCHEDTEST;
		
		System.err.println("In parseWhichSchedTest() No such sched test! System exit.");
		System.exit(1);
		return 0;
	}
	
	public static int parseSBFType(String str){
		if(str.equalsIgnoreCase("MPR2")) return GlobalVariable.MPR_SBF_ARVIND;
		if(str.equalsIgnoreCase("MPR2_Meng")) return GlobalVariable.MPR_SBF_MENG;
		
		System.err.println("In parseSBFType() for MPR model! only uspport MPR2 and MPR2_Meng model! System exit.");
		System.exit(1);
		return 0;
	}
	
	private static void error() {
		System.err.println("Invalid arguments");
		System.err
				.println("Carts <input_XML_file> <scheduling_algo> <output_XML_file>");
		System.err
		.println("<scheduling_algo> can be : PRM / EDP / EQV / MPR / DMPR / CADMPR_TASKCENTRIC / CADMPR_MODELCENTRIC / CADMPR_HYBRID");
		System.exit(1);
		
	}
	
	public static String doCSA_start(Component rootComponent, int whichSchedTest, int sbf_type){
		String result = checkSchedulingAlgorithm(rootComponent);
		if(!result.toUpperCase().contains("FAIL")){
			rootComponent.doCSA(whichSchedTest,sbf_type, result);
			result = "SUCCESS"; //compute succeed.
		}else{
			System.err.println("Only support gEDF and gDM and all component must be same sched. algorithm.");
		}
		return result;
	}
	
	public static String checkSchedulingAlgorithm(Component rootComponent){
		String result = "";
		if(rootComponent.getSchedulingPolicy().equalsIgnoreCase("EDF") || rootComponent
				.getSchedulingPolicy().equalsIgnoreCase("gEDF")){
			result = "gEDF";
		}else if(rootComponent.getSchedulingPolicy().equalsIgnoreCase("gDM") || rootComponent
				.getSchedulingPolicy().equalsIgnoreCase("DM")){
			result = "gDM";
		}else{
			result = "CHECK ALGORITHM FAIL";
		}
		
//		
//		if (!(rootComponent.getSchedulingPolicy().equalsIgnoreCase("EDF") || rootComponent
//				.getSchedulingPolicy().equalsIgnoreCase("gEDF") ||
//				rootComponent.getSchedulingPolicy().equalsIgnoreCase("gDM") || rootComponent
//				.getSchedulingPolicy().equalsIgnoreCase("DM"))) {
//			return "ERROR: only support gEDF/gDM scheduling policy in each component with MPR model";
//		}
		for (Component component : rootComponent.getChildComponents()) {
			// EDF/DM is considered as gEDF/gDM by default
			String child_result = checkSchedulingAlgorithm(component);
			if(!child_result.equals(result))
				return "CHECK ALGORITHM FAIL";
		}

		return result;
	}
}
